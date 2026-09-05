import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
USER_SESSION_PREFIX = "ai3_user_"
INVITE_PREFIX = "ai3_inv_"
TOKEN_PREFIX = "ai3_"


def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def now():
    return datetime.now(timezone.utc).isoformat()


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 131072, 8, 1
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


def install(app: FastAPI):
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            principal_id INTEGER NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(principal_id) REFERENCES principals(id)
        );
        CREATE TABLE IF NOT EXISTS user_agents (
            user_id INTEGER NOT NULL,
            agent_principal_id INTEGER NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(agent_principal_id) REFERENCES principals(id)
        );
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(username) REFERENCES users(username)
        );
        CREATE TABLE IF NOT EXISTS principal_limits (
            principal_id INTEGER PRIMARY KEY,
            rate_limit_rpm INTEGER NOT NULL DEFAULT 0,
            daily_request_limit INTEGER NOT NULL DEFAULT 0,
            max_input_tokens INTEGER NOT NULL DEFAULT 0,
            max_output_tokens INTEGER NOT NULL DEFAULT 0,
            max_concurrent_requests INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(principal_id) REFERENCES principals(id)
        );
        CREATE INDEX IF NOT EXISTS idx_user_sessions_hash ON user_sessions(token_hash);
        CREATE INDEX IF NOT EXISTS idx_user_agents_user ON user_agents(user_id);
        """)

    class InviteCreate(BaseModel):
        username: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
        email: Optional[str] = Field(default=None, max_length=320)
        expires_hours: int = Field(default=72, ge=1, le=720)

    class InviteAccept(BaseModel):
        invitation: str = Field(min_length=10, max_length=512)
        password: str = Field(min_length=12, max_length=256)

    class UserLogin(BaseModel):
        username: str = Field(min_length=1, max_length=100)
        password: str = Field(min_length=1, max_length=256)

    class AgentCreate(BaseModel):
        name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")

    class UserLimitsUpdate(BaseModel):
        rate_limit_rpm: int = Field(ge=0, le=1000000)
        daily_request_limit: int = Field(ge=0, le=100000000)
        max_input_tokens: int = Field(ge=0, le=100000000)
        max_output_tokens: int = Field(ge=0, le=100000000)
        max_concurrent_requests: int = Field(ge=0, le=100000)

    def require_user(x_ai3_user_session: Optional[str] = Header(default=None)):
        if not x_ai3_user_session or not x_ai3_user_session.startswith(USER_SESSION_PREFIX):
            raise HTTPException(401, "user session required")
        with db() as con:
            row = con.execute("""
                SELECT u.*, p.name AS principal_name, p.active AS principal_active
                FROM user_sessions s JOIN users u ON u.id=s.user_id
                JOIN principals p ON p.id=u.principal_id
                WHERE s.token_hash=? AND s.active=1
            """, (hash_value(x_ai3_user_session),)).fetchone()
            if not row:
                raise HTTPException(401, "invalid user session")
            if row["expires_at"] <= now():
                con.execute("UPDATE user_sessions SET active=0 WHERE token_hash=?", (hash_value(x_ai3_user_session),))
                raise HTTPException(401, "user session expired")
            if not row["active"] or not row["principal_active"]:
                raise HTTPException(403, "user is inactive")
            return row

    @app.post("/v1/admin/users/invitations", dependencies=[Depends(__import__('app.main', fromlist=['require_admin']).require_admin)])
    def create_invitation(body: InviteCreate):
        expires = datetime.now(timezone.utc) + timedelta(hours=body.expires_hours)
        raw = INVITE_PREFIX + secrets.token_urlsafe(32)
        with db() as con:
            if con.execute("SELECT 1 FROM users WHERE username=?", (body.username,)).fetchone():
                raise HTTPException(409, "username already exists")
            if con.execute("SELECT 1 FROM invitations WHERE username=? AND used_at IS NULL", (body.username,)).fetchone():
                raise HTTPException(409, "active invitation already exists")
            con.execute("INSERT INTO invitations(token_hash,username,email,expires_at,created_at) VALUES(?,?,?,?,?)", (hash_value(raw), body.username, body.email, expires.isoformat(), now()))
        return {"invitation": raw, "username": body.username, "email": body.email, "expires_at": expires.isoformat()}

    @app.get("/v1/admin/users", dependencies=[Depends(__import__('app.main', fromlist=['require_admin']).require_admin)])
    def list_users():
        with db() as con:
            rows = con.execute("""
                SELECT u.id,u.username,u.email,u.created_at,u.active,p.name AS principal_name,
                       (SELECT COUNT(*) FROM user_agents ua WHERE ua.user_id=u.id) AS agents
                FROM users u JOIN principals p ON p.id=u.principal_id ORDER BY u.id
            """).fetchall()
        return [dict(r) for r in rows]

    @app.post("/v1/auth/invitations/accept")
    def accept_invitation(body: InviteAccept):
        with db() as con:
            inv = con.execute("SELECT * FROM invitations WHERE token_hash=? AND used_at IS NULL", (hash_value(body.invitation),)).fetchone()
            if not inv:
                raise HTTPException(400, "invalid or already used invitation")
            if inv["expires_at"] <= now():
                raise HTTPException(400, "invitation expired")
            try:
                cur = con.execute("INSERT INTO principals(name,kind,created_at) VALUES(?,?,?)", (f"user:{inv['username']}", "user", now()))
                principal_id = cur.lastrowid
                cur = con.execute("INSERT INTO users(principal_id,username,email,password_hash,created_at) VALUES(?,?,?,?,?)", (principal_id, inv["username"], inv["email"], hash_password(body.password), now()))
                user_id = cur.lastrowid
                con.execute("INSERT INTO principal_limits(principal_id,updated_at) VALUES(?,?)", (principal_id, now()))
                con.execute("UPDATE invitations SET used_at=? WHERE id=?", (now(), inv["id"]))
            except sqlite3.IntegrityError:
                raise HTTPException(409, "username already exists")
        return {"ok": True, "username": inv["username"], "message": "account created; use /v1/auth/login"}

    @app.post("/v1/auth/login")
    def user_login(body: UserLogin):
        with db() as con:
            row = con.execute("SELECT * FROM users WHERE username=? AND active=1", (body.username,)).fetchone()
        if not row or not verify_password(body.password, row["password_hash"]):
            raise HTTPException(401, "invalid username or password")
        raw = USER_SESSION_PREFIX + secrets.token_urlsafe(48)
        expires = datetime.now(timezone.utc) + timedelta(hours=24)
        with db() as con:
            con.execute("INSERT INTO user_sessions(user_id,token_hash,created_at,expires_at) VALUES(?,?,?,?,?)", (row["id"], hash_value(raw), now(), expires.isoformat()))
        return {"session": raw, "token_type": "AI3-User-Session", "expires_at": expires.isoformat(), "username": row["username"]}

    @app.post("/v1/auth/logout", dependencies=[Depends(require_user)])
    def user_logout(x_ai3_user_session: Optional[str] = Header(default=None)):
        with db() as con:
            con.execute("UPDATE user_sessions SET active=0 WHERE token_hash=?", (hash_value(x_ai3_user_session or ""),))
        return {"ok": True}

    @app.get("/v1/user/me", dependencies=[Depends(require_user)])
    def user_me(user=Depends(require_user)):
        with db() as con:
            agents = con.execute("""
                SELECT p.id,p.name,p.created_at,p.active FROM user_agents ua
                JOIN principals p ON p.id=ua.agent_principal_id WHERE ua.user_id=? ORDER BY p.id
            """, (user["id"],)).fetchall()
        return {"id": user["id"], "username": user["username"], "email": user["email"], "agents": [dict(x) for x in agents]}

    @app.post("/v1/user/agents", dependencies=[Depends(require_user)])
    def create_agent(body: AgentCreate, user=Depends(require_user)):
        full_name = f"{user['username']}:{body.name}"
        with db() as con:
            if con.execute("SELECT 1 FROM principals WHERE name=?", (full_name,)).fetchone():
                raise HTTPException(409, "agent already exists")
            cur = con.execute("INSERT INTO principals(name,kind,created_at) VALUES(?,?,?)", (full_name, "agent", now()))
            agent_id = cur.lastrowid
            con.execute("INSERT INTO user_agents(user_id,agent_principal_id,created_at) VALUES(?,?,?)", (user["id"], agent_id, now()))
            con.execute("INSERT INTO principal_limits(principal_id,updated_at) VALUES(?,?)", (agent_id, now()))
        return {"id": agent_id, "name": full_name, "kind": "agent", "owner": user["username"]}

    @app.post("/v1/user/agents/{agent_id}/tokens", dependencies=[Depends(require_user)])
    def create_agent_token(agent_id: int, user=Depends(require_user)):
        with db() as con:
            agent = con.execute("""
                SELECT p.* FROM user_agents ua JOIN principals p ON p.id=ua.agent_principal_id
                WHERE ua.user_id=? AND p.id=? AND p.active=1
            """, (user["id"], agent_id)).fetchone()
            if not agent:
                raise HTTPException(404, "agent not found")
            raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
            con.execute("INSERT INTO tokens(principal_id,token_hash,prefix,name,scopes,created_at) VALUES(?,?,?,?,?,?)", (agent_id, hash_value(raw), raw[:12], "user-agent", "ai:inference,agents:read", now()))
        return {"token": raw, "token_prefix": raw[:12], "agent": agent["name"], "scopes": ["ai:inference", "agents:read"]}

    @app.get("/v1/user/agents/{agent_id}/limits", dependencies=[Depends(require_user)])
    def get_agent_limits(agent_id: int, user=Depends(require_user)):
        with db() as con:
            owned = con.execute("SELECT 1 FROM user_agents WHERE user_id=? AND agent_principal_id=?", (user["id"], agent_id)).fetchone()
            if not owned:
                raise HTTPException(404, "agent not found")
            row = con.execute("SELECT rate_limit_rpm,daily_request_limit,max_input_tokens,max_output_tokens,max_concurrent_requests FROM principal_limits WHERE principal_id=?", (agent_id,)).fetchone()
        return {"agent_id": agent_id, "limits": dict(row) if row else {}}

    @app.put("/v1/user/agents/{agent_id}/limits", dependencies=[Depends(require_user)])
    def set_agent_limits(agent_id: int, body: UserLimitsUpdate, user=Depends(require_user)):
        with db() as con:
            owned = con.execute("SELECT 1 FROM user_agents WHERE user_id=? AND agent_principal_id=?", (user["id"], agent_id)).fetchone()
            if not owned:
                raise HTTPException(404, "agent not found")
            con.execute("""INSERT INTO principal_limits(principal_id,rate_limit_rpm,daily_request_limit,max_input_tokens,max_output_tokens,max_concurrent_requests,updated_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(principal_id) DO UPDATE SET rate_limit_rpm=excluded.rate_limit_rpm,daily_request_limit=excluded.daily_request_limit,max_input_tokens=excluded.max_input_tokens,max_output_tokens=excluded.max_output_tokens,max_concurrent_requests=excluded.max_concurrent_requests,updated_at=excluded.updated_at""", (agent_id, body.rate_limit_rpm, body.daily_request_limit, body.max_input_tokens, body.max_output_tokens, body.max_concurrent_requests, now()))
        return {"agent_id": agent_id, "limits": body.model_dump()}

    return app
