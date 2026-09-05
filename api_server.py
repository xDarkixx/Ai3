import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
ADMIN_KEY = os.getenv("AI3_ADMIN_KEY", "")
OLLAMA_URL = os.getenv("AI3_OLLAMA_URL", "http://ollama:11434")

api = FastAPI(title="AI3 API Server", version="1.0.0")


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'unknown',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """)


@api.on_event("startup")
def startup():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    init_db()


def admin(x_ai3_admin_key: str | None):
    if not ADMIN_KEY or not x_ai3_admin_key or not secrets.compare_digest(x_ai3_admin_key, ADMIN_KEY):
        raise HTTPException(401, "invalid admin key")


def token_ok(authorization: str | None):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bearer token required")
    raw = authorization[7:].strip()
    with db() as con:
        row = con.execute("SELECT active,expires_at,scopes FROM tokens WHERE token_hash=?", (hashlib.sha256(raw.encode()).hexdigest(),)).fetchone()
    if not row or not row["active"] or (row["expires_at"] and row["expires_at"] <= now()):
        raise HTTPException(401, "invalid or expired token")
    if "ai:inference" not in row["scopes"].split(",") and "admin" not in row["scopes"].split(","):
        raise HTTPException(403, "missing scope: ai:inference")


class PullRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:/-]+$")


@api.get("/health")
def health():
    return {"status": "ok", "service": "ai3-api-server", "ollama": OLLAMA_URL}


@api.get("/api/v1/models")
async def models(authorization: str | None = Header(default=None)):
    token_ok(authorization)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{OLLAMA_URL}/api/tags")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:1000])
    data = r.json()
    with db() as con:
        for model in data.get("models", []):
            name = model.get("name")
            if name:
                con.execute("INSERT INTO models(name,status,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET status='ready',updated_at=excluded.updated_at", (name, "ready", now(), now()))
    return data


@api.post("/api/v1/models/pull")
async def pull_model(body: PullRequest, x_ai3_admin_key: str | None = Header(default=None)):
    admin(x_ai3_admin_key)
    with db() as con:
        con.execute("INSERT INTO models(name,status,created_at,updated_at) VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET status='downloading',updated_at=excluded.updated_at", (body.name, "downloading", now(), now()))
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(f"{OLLAMA_URL}/api/pull", json={"name": body.name, "stream": False})
    status_value = "ready" if r.status_code < 400 else "error"
    with db() as con:
        con.execute("UPDATE models SET status=?,updated_at=? WHERE name=?", (status_value, now(), body.name))
        con.execute("INSERT INTO api_events(endpoint,status_code,created_at) VALUES(?,?,?)", ("/api/v1/models/pull", r.status_code, now()))
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:1000])
    return {"ok": True, "model": body.name, "status": "ready"}


@api.get("/api/v1/status")
def status(authorization: str | None = Header(default=None)):
    token_ok(authorization)
    with db() as con:
        model_count = con.execute("SELECT COUNT(*) FROM models WHERE status='ready'").fetchone()[0]
        event_count = con.execute("SELECT COUNT(*) FROM api_events").fetchone()[0]
    return {"service": "AI3 API Server", "version": api.version, "ready_models": model_count, "api_events": event_count}
