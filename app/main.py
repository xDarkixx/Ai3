import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
ADMIN_KEY = os.getenv("AI3_ADMIN_KEY", "")
TOKEN_PREFIX = "ai3_"
LLM_BASE_URL = os.getenv("AI3_LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("AI3_LLM_API_KEY", "")
LLM_TIMEOUT = float(os.getenv("AI3_LLM_TIMEOUT", "300"))
OLLAMA_URL = os.getenv("AI3_OLLAMA_URL", "http://ollama:11434").rstrip("/")

app = FastAPI(title="AI3 Token Server", version="2.2.0")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS principals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL CHECK(kind IN ('user','agent','service')),
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            principal_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            prefix TEXT NOT NULL,
            name TEXT NOT NULL,
            scopes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            expires_at TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(principal_id) REFERENCES principals(id)
        );
        CREATE INDEX IF NOT EXISTS idx_tokens_hash ON tokens(token_hash);
        CREATE INDEX IF NOT EXISTS idx_tokens_principal ON tokens(principal_id);
        """)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", include_in_schema=False)
def web_home():
    return FileResponse(WEB_DIR / "index.html")


class PrincipalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(pattern="^(user|agent|service)$")


class TokenCreate(BaseModel):
    principal: str
    name: str = Field(default="default", min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["ai:inference"])
    expires_at: Optional[str] = None


class ModelPull(BaseModel):
    name: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:/-]+$")


def require_admin(x_ai3_admin_key: Optional[str] = Header(default=None)):
    if not ADMIN_KEY or not x_ai3_admin_key or not secrets.compare_digest(x_ai3_admin_key, ADMIN_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_principal(token: str):
    if not token.startswith(TOKEN_PREFIX):
        return None
    with db() as con:
        row = con.execute("""
            SELECT t.*, p.name AS principal_name, p.kind AS principal_kind, p.active AS principal_active
            FROM tokens t JOIN principals p ON p.id=t.principal_id
            WHERE t.token_hash=? AND t.active=1
        """, (hash_token(token),)).fetchone()
        if row:
            con.execute("UPDATE tokens SET last_used_at=? WHERE id=?", (now(), row["id"]))
        return row


def bearer(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    row = get_principal(authorization[7:].strip())
    if not row or not row["principal_active"]:
        raise HTTPException(status_code=401, detail="invalid or inactive token")
    if row["expires_at"] and row["expires_at"] <= now():
        raise HTTPException(status_code=401, detail="token expired")
    return row


def require_scope(row, scope: str):
    scopes = set(row["scopes"].split(",")) if row["scopes"] else set()
    if scope not in scopes and "admin" not in scopes:
        raise HTTPException(403, f"missing scope: {scope}")


def upstream_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
    return headers


def upstream_url(path: str) -> str:
    if not LLM_BASE_URL:
        raise HTTPException(503, "AI3_LLM_BASE_URL is not configured")
    return f"{LLM_BASE_URL}{path}"


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai3-token-server", "time": now(), "llm_configured": bool(LLM_BASE_URL)}


@app.post("/v1/principals", dependencies=[Depends(require_admin)])
def create_principal(body: PrincipalCreate):
    with db() as con:
        try:
            cur = con.execute("INSERT INTO principals(name,kind,created_at) VALUES(?,?,?)", (body.name, body.kind, now()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "principal already exists")
        return {"id": cur.lastrowid, "name": body.name, "kind": body.kind}


@app.post("/v1/tokens", dependencies=[Depends(require_admin)])
def create_token(body: TokenCreate):
    with db() as con:
        p = con.execute("SELECT * FROM principals WHERE name=? AND active=1", (body.principal,)).fetchone()
        if not p:
            raise HTTPException(404, "principal not found")
        raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
        con.execute("INSERT INTO tokens(principal_id,token_hash,prefix,name,scopes,created_at,expires_at) VALUES(?,?,?,?,?,?,?)",
                    (p["id"], hash_token(raw), raw[:12], body.name, ",".join(sorted(set(body.scopes))), now(), body.expires_at))
        return {"token": raw, "token_prefix": raw[:12], "principal": p["name"], "scopes": sorted(set(body.scopes)), "expires_at": body.expires_at}


@app.get("/v1/admin/principals", dependencies=[Depends(require_admin)])
def admin_principals():
    with db() as con:
        rows = con.execute("SELECT id,name,kind,created_at,active FROM principals ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.get("/v1/admin/tokens", dependencies=[Depends(require_admin)])
def admin_tokens():
    with db() as con:
        rows = con.execute("""
            SELECT t.prefix,t.name,t.scopes,t.created_at,t.last_used_at,t.expires_at,t.active,
                   p.name AS principal
            FROM tokens t JOIN principals p ON p.id=t.principal_id ORDER BY t.id DESC
        """).fetchall()
    return [dict(r) for r in rows]


@app.get("/v1/admin/models", dependencies=[Depends(require_admin)])
async def admin_models():
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        response = await client.get(upstream_url("/models"), headers=upstream_headers())
    if response.status_code >= 400:
        raise HTTPException(response.status_code, response.text[:1000])
    return response.json()


@app.get("/v1/admin/local-models", dependencies=[Depends(require_admin)])
async def admin_local_models():
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{OLLAMA_URL}/api/tags")
    if response.status_code >= 400:
        raise HTTPException(response.status_code, response.text[:1000])
    return response.json()


@app.post("/v1/admin/local-models/pull", dependencies=[Depends(require_admin)])
async def admin_pull_model(body: ModelPull):
    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.post(f"{OLLAMA_URL}/api/pull", json={"name": body.name, "stream": False})
    if response.status_code >= 400:
        raise HTTPException(response.status_code, response.text[:1000])
    return {"ok": True, "model": body.name, "status": "ready", "ollama": response.json()}


@app.get("/v1/admin/status", dependencies=[Depends(require_admin)])
async def admin_status():
    local = await admin_local_models()
    return {"service": "AI3", "version": app.version, "gateway": "online", "local_models": len(local.get("models", [])), "llm_configured": bool(LLM_BASE_URL)}


@app.get("/v1/me")
def me(row=Depends(bearer)):
    return {"principal": row["principal_name"], "kind": row["principal_kind"], "scopes": row["scopes"].split(",") if row["scopes"] else []}


@app.post("/v1/tokens/revoke", dependencies=[Depends(require_admin)])
def revoke_token(token_prefix: str):
    with db() as con:
        cur = con.execute("UPDATE tokens SET active=0 WHERE prefix=?", (token_prefix,))
        if cur.rowcount == 0:
            raise HTTPException(404, "token not found")
    return {"revoked": True, "token_prefix": token_prefix}


@app.get("/v1/agents")
def agents(row=Depends(bearer)):
    require_scope(row, "agents:read")
    with db() as con:
        rows = con.execute("SELECT id,name,kind,created_at FROM principals WHERE active=1 ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.get("/v1/models")
async def models(row=Depends(bearer)):
    require_scope(row, "ai:inference")
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        response = await client.get(upstream_url("/models"), headers=upstream_headers())
    return _upstream_response(response)


@app.get("/v1/models/{model_id}")
async def model(model_id: str, row=Depends(bearer)):
    require_scope(row, "ai:inference")
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        response = await client.get(upstream_url(f"/models/{model_id}"), headers=upstream_headers())
    return _upstream_response(response)


async def _proxy_json(request: Request, path: str):
    body = await request.body()
    headers = upstream_headers()
    content_type = request.headers.get("content-type")
    if content_type:
        headers["Content-Type"] = content_type
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        response = await client.post(upstream_url(path), content=body, headers=headers)
    return _upstream_response(response)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, row=Depends(bearer)):
    require_scope(row, "ai:inference")
    body = await request.body()
    headers = upstream_headers()
    headers["Content-Type"] = request.headers.get("content-type", "application/json")
    try:
        import json
        payload = json.loads(body or b"{}")
    except Exception:
        raise HTTPException(400, "invalid JSON body")
    if payload.get("stream") is not True:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            response = await client.post(upstream_url("/chat/completions"), content=body, headers=headers)
        return _upstream_response(response)

    async def stream():
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            async with client.stream("POST", upstream_url("/chat/completions"), content=body, headers=headers) as response:
                if response.status_code >= 400:
                    detail = await response.aread()
                    yield detail
                    return
                async for chunk in response.aiter_raw():
                    yield chunk

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/v1/responses")
async def responses(request: Request, row=Depends(bearer)):
    require_scope(row, "ai:inference")
    return await _proxy_json(request, "/responses")


@app.post("/v1/embeddings")
async def embeddings(request: Request, row=Depends(bearer)):
    require_scope(row, "ai:inference")
    return await _proxy_json(request, "/embeddings")


def _upstream_response(response: httpx.Response):
    from fastapi.responses import Response
    content_type = response.headers.get("content-type", "application/json")
    return Response(content=response.content, status_code=response.status_code, media_type=content_type.split(";", 1)[0])
