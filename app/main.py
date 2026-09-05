import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
ADMIN_KEY = os.getenv("AI3_ADMIN_KEY", "")
INITIAL_ADMIN_PASSWORD = os.getenv("AI3_ADMIN_PASSWORD", "")
TOKEN_PREFIX = "ai3_"
ADMIN_SESSION_PREFIX = "ai3_admin_"
LLM_BASE_URL = os.getenv("AI3_LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("AI3_LLM_API_KEY", "")
LLM_TIMEOUT = float(os.getenv("AI3_LLM_TIMEOUT", "300"))
OLLAMA_URL = os.getenv("AI3_OLLAMA_URL", "http://ollama:11434").rstrip("/")
VLLM_URL = os.getenv("AI3_VLLM_URL", "").rstrip("/")
LLAMACPP_URL = os.getenv("AI3_LLAMACPP_URL", "").rstrip("/")
BACKEND = os.getenv("AI3_BACKEND", "ollama")
ADMIN_SESSION_HOURS = int(os.getenv("AI3_ADMIN_SESSION_HOURS", "12"))

app = FastAPI(title="AI3 Universal AI Gateway", version="3.1.0")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    # 32768 is deliberately used here so password changes also work on
    # constrained CI/container environments. The encoded parameters allow
    # future verification of hashes created with older settings.
    n, r, p = 32768, 8, 1
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, n, r, p, salt_hex, digest_hex = encoded.split("$", 5)
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=32)
        return secrets.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS principals (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, kind TEXT NOT NULL CHECK(kind IN ('user','agent','service')), created_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, principal_id INTEGER NOT NULL, token_hash TEXT NOT NULL UNIQUE, prefix TEXT NOT NULL, name TEXT NOT NULL, scopes TEXT NOT NULL, created_at TEXT NOT NULL, last_used_at TEXT, expires_at TEXT, active INTEGER NOT NULL DEFAULT 1, FOREIGN KEY(principal_id) REFERENCES principals(id));
        CREATE INDEX IF NOT EXISTS idx_tokens_hash ON tokens(token_hash);
        CREATE INDEX IF NOT EXISTS idx_tokens_principal ON tokens(principal_id);
        CREATE TABLE IF NOT EXISTS agent_configs (principal_id INTEGER PRIMARY KEY, model TEXT, backend TEXT NOT NULL DEFAULT 'ollama', system_prompt TEXT, updated_at TEXT NOT NULL, FOREIGN KEY(principal_id) REFERENCES principals(id));
        CREATE TABLE IF NOT EXISTS usage_events (id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint TEXT NOT NULL, principal_id INTEGER, status_code INTEGER NOT NULL, duration_ms INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, FOREIGN KEY(principal_id) REFERENCES principals(id));
        CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_events(created_at);
        CREATE TABLE IF NOT EXISTS admin_settings (name TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admin_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE INDEX IF NOT EXISTS idx_admin_sessions_hash ON admin_sessions(token_hash);
        """)
        if INITIAL_ADMIN_PASSWORD:
            exists = con.execute("SELECT 1 FROM admin_settings WHERE name='password_hash'").fetchone()
            if not exists:
                con.execute("INSERT INTO admin_settings(name,value,updated_at) VALUES('password_hash',?,?)", (hash_password(INITIAL_ADMIN_PASSWORD), now()))


@app.on_event("startup")
def startup():
    init_db()


@app.middleware("http")
async def usage_middleware(request: Request, call_next):
    started = datetime.now(timezone.utc)
    response = await call_next(request)
    principal_id = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        raw = auth[7:].strip()
        try:
            with db() as con:
                row = con.execute("SELECT principal_id FROM tokens WHERE token_hash=?", (hash_token(raw),)).fetchone()
                principal_id = row[0] if row else None
        except Exception:
            principal_id = None
    duration = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    try:
        with db() as con:
            con.execute("INSERT INTO usage_events(endpoint,principal_id,status_code,duration_ms,created_at) VALUES(?,?,?,?,?)", (request.url.path, principal_id, response.status_code, duration, now()))
    except Exception:
        pass
    return response


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


class TokenRotate(BaseModel):
    token_prefix: str


class AdminPasswordChange(BaseModel):
    current_password: Optional[str] = None
    new_password: str = Field(min_length=12, max_length=256)


def require_admin(x_ai3_admin_key: Optional[str] = Header(default=None), x_ai3_admin_session: Optional[str] = Header(default=None)):
    if ADMIN_KEY and secrets.compare_digest(x_ai3_admin_key or "", ADMIN_KEY):
        return True
    if x_ai3_admin_session:
        with db() as con:
            row = con.execute("SELECT 1 FROM admin_sessions WHERE token_hash=? AND active=1 AND expires_at>?", (hash_token(x_ai3_admin_session), now())).fetchone()
        if row:
            return True
    raise HTTPException(401, "admin authentication required")


def bearer(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "bearer token required")
    raw = authorization[7:].strip()
    with db() as con:
        row = con.execute("SELECT t.*,p.name AS principal_name,p.kind AS principal_kind FROM tokens t JOIN principals p ON p.id=t.principal_id WHERE t.token_hash=? AND t.active=1 AND p.active=1", (hash_token(raw),)).fetchone()
    if not row:
        raise HTTPException(401, "invalid or revoked token")
    if row["expires_at"] and row["expires_at"] <= now():
        raise HTTPException(401, "token expired")
    with db() as con:
        con.execute("UPDATE tokens SET last_used_at=? WHERE id=?", (now(), row["id"]))
    return row


def require_scope(row, scope: str):
    scopes = set(filter(None, (row["scopes"] or "").split(",")))
    if scope not in scopes:
        raise HTTPException(403, f"missing scope: {scope}")


@app.get("/health")
def health():
    return {"service": "ai3-gateway", "version": app.version, "status": "ok"}


@app.post("/v1/admin/password", dependencies=[Depends(require_admin)])
def change_admin_password(body: AdminPasswordChange):
    with db() as con:
        row = con.execute("SELECT value FROM admin_settings WHERE name='password_hash'").fetchone()
        if row:
            if not body.current_password or not verify_password(body.current_password, row["value"]):
                raise HTTPException(401, "current admin password is required")
        elif not ADMIN_KEY:
            raise HTTPException(503, "no bootstrap admin credential configured")
        con.execute("INSERT INTO admin_settings(name,value,updated_at) VALUES('password_hash',?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", (hash_password(body.new_password), now()))
        con.execute("UPDATE admin_sessions SET active=0 WHERE expires_at<=?", (now(),))
    return {"ok": True, "message": "admin password changed"}


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
        scopes = sorted(set(body.scopes))
        con.execute("INSERT INTO tokens(principal_id,token_hash,prefix,name,scopes,created_at,expires_at) VALUES(?,?,?,?,?,?,?)", (p["id"], hash_token(raw), raw[:12], body.name, ",".join(scopes), now(), body.expires_at))
        return {"token": raw, "token_prefix": raw[:12], "principal": p["name"], "scopes": scopes, "expires_at": body.expires_at}


@app.post("/v1/tokens/revoke", dependencies=[Depends(require_admin)])
def revoke_token(token_prefix: str):
    with db() as con:
        cur = con.execute("UPDATE tokens SET active=0 WHERE prefix=? AND active=1", (token_prefix,))
    if cur.rowcount == 0:
        raise HTTPException(404, "active token not found")
    return {"ok": True, "token_prefix": token_prefix, "status": "revoked"}


@app.post("/v1/tokens/rotate", dependencies=[Depends(require_admin)])
def rotate_token(body: TokenRotate):
    with db() as con:
        old = con.execute("SELECT t.*,p.name AS principal FROM tokens t JOIN principals p ON p.id=t.principal_id WHERE t.prefix=? AND t.active=1", (body.token_prefix,)).fetchone()
        if not old:
            raise HTTPException(404, "active token not found")
        raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
        con.execute("UPDATE tokens SET active=0 WHERE id=?", (old["id"],))
        con.execute("INSERT INTO tokens(principal_id,token_hash,prefix,name,scopes,created_at,expires_at) VALUES(?,?,?,?,?,?,?)", (old["principal_id"], hash_token(raw), raw[:12], old["name"], old["scopes"], now(), old["expires_at"]))
    return {"token": raw, "token_prefix": raw[:12], "principal": old["principal"], "scopes": old["scopes"].split(",") if old["scopes"] else [], "expires_at": old["expires_at"]}


@app.get("/v1/admin/principals", dependencies=[Depends(require_admin)])
def admin_principals():
    with db() as con:
        rows = con.execute("SELECT id,name,kind,created_at,active FROM principals ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.get("/v1/admin/tokens", dependencies=[Depends(require_admin)])
def admin_tokens():
    with db() as con:
        rows = con.execute("SELECT t.prefix,t.name,t.scopes,t.created_at,t.last_used_at,t.expires_at,t.active,p.name AS principal FROM tokens t JOIN principals p ON p.id=t.principal_id ORDER BY t.id DESC").fetchall()
    return [dict(r) for r in rows]


class ModelPull(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class AgentConfig(BaseModel):
    model: Optional[str] = None
    backend: str = "ollama"
    system_prompt: Optional[str] = None


async def probe_backend(name: str, base_url: str):
    result = {"name": name, "url": base_url, "online": False, "models": 0}
    if not base_url:
        result["configured"] = False
        return result
    result["configured"] = True
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            if name == "ollama":
                response = await client.get(f"{base_url}/api/tags")
                if response.status_code < 400:
                    result["models"] = len(response.json().get("models", []))
            else:
                response = await client.get(f"{base_url}/v1/models")
                if response.status_code < 400:
                    result["models"] = len(response.json().get("data", []))
            result["online"] = response.status_code < 400
    except Exception as exc:
        result["error"] = type(exc).__name__
    return result


@app.get("/v1/admin/backends", dependencies=[Depends(require_admin)])
async def admin_backends():
    return {"selected": BACKEND, "backends": [
        await probe_backend("ollama", OLLAMA_URL),
        await probe_backend("vllm", VLLM_URL),
        await probe_backend("llamacpp", LLAMACPP_URL),
        await probe_backend("openai-compatible", LLM_BASE_URL),
    ]}


@app.get("/v1/admin/models", dependencies=[Depends(require_admin)])
async def admin_models():
    if LLM_BASE_URL:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            response = await client.get(upstream_url("/models"), headers=upstream_headers())
        if response.status_code < 400:
            return response.json()
    return {"object": "list", "data": []}


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
    local_models = 0
    ollama_status = "offline"
    try:
        local = await admin_local_models()
        local_models = len(local.get("models", []))
        ollama_status = "online"
    except Exception:
        pass
    with db() as con:
        principals = con.execute("SELECT COUNT(*) FROM principals WHERE active=1").fetchone()[0]
        tokens = con.execute("SELECT COUNT(*) FROM tokens WHERE active=1").fetchone()[0]
        requests = con.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0]
    return {"service": "AI3", "version": app.version, "gateway": "online", "ollama": ollama_status, "local_models": local_models, "principals": principals, "active_tokens": tokens, "requests": requests, "backend": BACKEND, "llm_configured": bool(LLM_BASE_URL)}


@app.get("/v1/admin/usage", dependencies=[Depends(require_admin)])
def admin_usage():
    with db() as con:
        total = con.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0]
        errors = con.execute("SELECT COUNT(*) FROM usage_events WHERE status_code >= 400").fetchone()[0]
        avg_ms = con.execute("SELECT COALESCE(AVG(duration_ms),0) FROM usage_events").fetchone()[0]
        endpoints = [dict(r) for r in con.execute("SELECT endpoint,COUNT(*) AS requests,COALESCE(AVG(duration_ms),0) AS avg_ms FROM usage_events GROUP BY endpoint ORDER BY requests DESC LIMIT 20").fetchall()]
        agents = [dict(r) for r in con.execute("SELECT COALESCE(p.name,'anonymous') AS principal,COUNT(*) AS requests FROM usage_events u LEFT JOIN principals p ON p.id=u.principal_id GROUP BY u.principal_id ORDER BY requests DESC LIMIT 20").fetchall()]
    return {"total_requests": total, "errors": errors, "error_rate": round(errors / total, 4) if total else 0, "avg_latency_ms": round(avg_ms, 1), "endpoints": endpoints, "agents": agents}


@app.get("/v1/admin/agents", dependencies=[Depends(require_admin)])
def admin_agents():
    with db() as con:
        rows = con.execute("SELECT p.id,p.name,p.kind,p.created_at,p.active,c.model,c.backend,c.system_prompt,c.updated_at FROM principals p LEFT JOIN agent_configs c ON c.principal_id=p.id WHERE p.kind='agent' ORDER BY p.id").fetchall()
    return [dict(r) for r in rows]


@app.put("/v1/admin/agents/{principal_id}", dependencies=[Depends(require_admin)])
def update_agent(principal_id: int, body: AgentConfig):
    with db() as con:
        p = con.execute("SELECT id,name,kind FROM principals WHERE id=? AND active=1", (principal_id,)).fetchone()
        if not p or p["kind"] != "agent":
            raise HTTPException(404, "agent not found")
        con.execute("INSERT INTO agent_configs(principal_id,model,backend,system_prompt,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(principal_id) DO UPDATE SET model=excluded.model,backend=excluded.backend,system_prompt=excluded.system_prompt,updated_at=excluded.updated_at", (principal_id, body.model, body.backend, body.system_prompt, now()))
    return {"ok": True, "agent": p["name"], **body.model_dump()}


@app.get("/v1/agents")
def agents(row=Depends(bearer)):
    require_scope(row, "agents:read")
    with db() as con:
        rows = con.execute("SELECT p.id,p.name,p.kind,p.created_at,c.model,c.backend FROM principals p LEFT JOIN agent_configs c ON c.principal_id=p.id WHERE p.active=1 ORDER BY p.id").fetchall()
    return [dict(r) for r in rows]


@app.get("/v1/me")
def me(row=Depends(bearer)):
    return {"principal": row["principal_name"], "kind": row["principal_kind"], "scopes": row["scopes"].split(",") if row["scopes"] else [], "token_prefix": row["prefix"], "expires_at": row["expires_at"]}


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


def upstream_url(path: str) -> str:
    base = LLM_BASE_URL
    if not base:
        return path
    return base + (path if path.startswith("/") else "/" + path)


def upstream_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
    return headers


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
                    yield await response.aread()
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


# Optional security/account extensions are installed here rather than through
# sitecustomize so they are also active in tests and direct Python launches.
if os.getenv("AI3_ENABLE_ADVANCED_SECURITY", "0") == "1":
    from app.advanced_security import install as install_security
    from app.rate_limit import install as install_rate_limit
    from app.runtime_controls import install as install_runtime_controls
    from app import user_accounts

    install_security(app)
    install_runtime_controls(app)
    user_accounts.install(app)
    install_rate_limit(app)
