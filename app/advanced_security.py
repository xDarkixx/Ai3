import hashlib
import os
import secrets
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
ACCESS_TOKEN_MINUTES = int(os.getenv("AI3_ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.getenv("AI3_REFRESH_TOKEN_DAYS", "30"))
RATE_LIMIT_RPM = int(os.getenv("AI3_RATE_LIMIT_RPM", "120"))
DAILY_REQUEST_LIMIT = int(os.getenv("AI3_DAILY_REQUEST_LIMIT", "0"))
BACKUP_DIR = Path(os.getenv("AI3_BACKUP_DIR", "/data/backups"))


def now_dt():
    return datetime.now(timezone.utc)


def now():
    return now_dt().isoformat()


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def init_advanced_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS oauth_clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL UNIQUE,
            client_secret_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            principal_id INTEGER NOT NULL,
            scopes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(principal_id) REFERENCES principals(id)
        );
        CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL,
            principal_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            scopes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(principal_id) REFERENCES principals(id)
        );
        CREATE INDEX IF NOT EXISTS idx_oauth_refresh_hash ON oauth_refresh_tokens(token_hash);
        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            principal_id INTEGER,
            client_id TEXT,
            created_at TEXT NOT NULL,
            metadata TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_security_events_created ON security_events(created_at);
        """)


def admin_dependency():
    from app.main import require_admin
    return require_admin


class OAuthClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    principal: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["ai:inference"])


class OAuthTokenRequest(BaseModel):
    grant_type: str
    client_id: str
    client_secret: str
    refresh_token: str | None = None
    scope: str | None = None


class OAuthRevokeRequest(BaseModel):
    token: str
    token_type_hint: str | None = None


def issue_refresh(client_id: str, principal_id: int, scopes: list[str]):
    raw = "ai3_rt_" + secrets.token_urlsafe(48)
    expires = now_dt() + timedelta(days=REFRESH_TOKEN_DAYS)
    with db() as con:
        con.execute(
            "INSERT INTO oauth_refresh_tokens(client_id,principal_id,token_hash,scopes,created_at,expires_at) VALUES(?,?,?,?,?,?)",
            (client_id, principal_id, h(raw), ",".join(sorted(set(scopes))), now(), expires.isoformat()),
        )
    return raw, expires


def issue_access(principal_id: int, scopes: list[str], client_id: str):
    raw = "ai3_" + secrets.token_urlsafe(32)
    expires = now_dt() + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    with db() as con:
        con.execute(
            "INSERT INTO tokens(principal_id,token_hash,prefix,name,scopes,created_at,expires_at) VALUES(?,?,?,?,?,?,?)",
            (principal_id, h(raw), raw[:12], f"oauth:{client_id}", ",".join(sorted(set(scopes))), now(), expires.isoformat()),
        )
    return raw, expires


def install(app: FastAPI):
    init_advanced_db()

    @app.on_event("startup")
    def advanced_startup():
        init_advanced_db()

    @app.post("/oauth/token")
    def oauth_token(body: OAuthTokenRequest):
        if body.grant_type not in {"client_credentials", "refresh_token"}:
            raise HTTPException(400, "unsupported grant_type")
        with db() as con:
            client = con.execute(
                "SELECT * FROM oauth_clients WHERE client_id=? AND active=1", (body.client_id,)
            ).fetchone()
        if not client or not secrets.compare_digest(h(body.client_secret), client["client_secret_hash"]):
            raise HTTPException(401, "invalid_client")

        allowed = set(client["scopes"].split(",")) if client["scopes"] else set()
        if body.grant_type == "client_credentials":
            scopes = sorted(allowed)
        else:
            if not body.refresh_token:
                raise HTTPException(400, "refresh_token required")
            with db() as con:
                old = con.execute(
                    "SELECT * FROM oauth_refresh_tokens WHERE token_hash=? AND client_id=? AND active=1",
                    (h(body.refresh_token), body.client_id),
                ).fetchone()
                if not old or old["expires_at"] <= now():
                    raise HTTPException(401, "invalid_grant")
                con.execute("UPDATE oauth_refresh_tokens SET active=0,used_at=? WHERE id=?", (now(), old["id"]))
            scopes = [x for x in old["scopes"].split(",") if x in allowed]
            if body.scope:
                requested = set(body.scope.split())
                scopes = [x for x in scopes if x in requested]

        access, access_exp = issue_access(client["principal_id"], scopes, body.client_id)
        refresh, refresh_exp = issue_refresh(body.client_id, client["principal_id"], scopes)
        with db() as con:
            con.execute(
                "INSERT INTO security_events(event,principal_id,client_id,created_at,metadata) VALUES(?,?,?,?,?)",
                ("oauth.token", client["principal_id"], body.client_id, now(), body.grant_type),
            )
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": max(1, int((access_exp - now_dt()).total_seconds())),
            "scope": " ".join(scopes),
            "refresh_token": refresh,
            "refresh_expires_in": max(1, int((refresh_exp - now_dt()).total_seconds())),
        }

    @app.post("/oauth/revoke")
    def oauth_revoke(body: OAuthRevokeRequest):
        with db() as con:
            con.execute("UPDATE tokens SET active=0 WHERE token_hash=?", (h(body.token),))
            con.execute("UPDATE oauth_refresh_tokens SET active=0,used_at=? WHERE token_hash=?", (now(), h(body.token)))
        return {"active": False}

    @app.post("/v1/admin/oauth/clients", dependencies=[Depends(admin_dependency())])
    def create_oauth_client(body: OAuthClientCreate):
        with db() as con:
            p = con.execute("SELECT id FROM principals WHERE name=? AND active=1", (body.principal,)).fetchone()
            if not p:
                raise HTTPException(404, "principal not found")
            client_id = "ai3_client_" + secrets.token_urlsafe(18)
            client_secret = "ai3_secret_" + secrets.token_urlsafe(32)
            scopes = sorted(set(body.scopes))
            con.execute(
                "INSERT INTO oauth_clients(client_id,client_secret_hash,name,principal_id,scopes,created_at) VALUES(?,?,?,?,?,?)",
                (client_id, h(client_secret), body.name, p["id"], ",".join(scopes), now()),
            )
        return {"client_id": client_id, "client_secret": client_secret, "name": body.name, "principal": body.principal, "scopes": scopes}

    @app.get("/v1/admin/oauth/clients", dependencies=[Depends(admin_dependency())])
    def list_oauth_clients():
        with db() as con:
            rows = con.execute(
                "SELECT c.client_id,c.name,c.scopes,c.created_at,c.active,p.name AS principal FROM oauth_clients c JOIN principals p ON p.id=c.principal_id ORDER BY c.id DESC"
            ).fetchall()
        return [dict(x) for x in rows]

    @app.delete("/v1/admin/oauth/clients/{client_id}", dependencies=[Depends(admin_dependency())])
    def disable_oauth_client(client_id: str):
        with db() as con:
            cur = con.execute("UPDATE oauth_clients SET active=0 WHERE client_id=? AND active=1", (client_id,))
            con.execute("UPDATE oauth_refresh_tokens SET active=0 WHERE client_id=?", (client_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "client not found")
        return {"ok": True, "client_id": client_id, "active": False}

    @app.get("/v1/admin/security/events", dependencies=[Depends(admin_dependency())])
    def security_events(limit: int = 100):
        limit = max(1, min(limit, 500))
        with db() as con:
            rows = con.execute("SELECT event,principal_id,client_id,created_at,metadata FROM security_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(x) for x in rows]

    @app.post("/v1/admin/backup", dependencies=[Depends(admin_dependency())])
    def backup_database():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        target = BACKUP_DIR / f"ai3-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.db"
        with db() as con:
            backup_con = sqlite3.connect(target)
            try:
                con.backup(backup_con)
            finally:
                backup_con.close()
        return {"ok": True, "file": str(target), "size_bytes": target.stat().st_size, "created_at": now()}

    @app.get("/v1/admin/backups", dependencies=[Depends(admin_dependency())])
    def list_backups():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        items = []
        for path in sorted(BACKUP_DIR.glob("ai3-*.db"), reverse=True):
            items.append({"file": path.name, "size_bytes": path.stat().st_size, "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
        return items[:100]

    return app
