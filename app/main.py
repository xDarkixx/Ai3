import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
ADMIN_KEY = os.getenv("AI3_ADMIN_KEY", "")
TOKEN_PREFIX = "ai3_"

app = FastAPI(title="AI3 Token Server", version="1.0.0")


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


class PrincipalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(pattern="^(user|agent|service)$")


class TokenCreate(BaseModel):
    principal: str
    name: str = Field(default="default", min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["ai:inference"])
    expires_at: Optional[str] = None


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


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai3-token-server", "time": now()}


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
    if "agents:read" not in row["scopes"].split(",") and "admin" not in row["scopes"].split(","):
        raise HTTPException(403, "missing scope: agents:read")
    with db() as con:
        rows = con.execute("SELECT id,name,kind,created_at FROM principals WHERE active=1 ORDER BY id").fetchall()
    return [dict(r) for r in rows]
