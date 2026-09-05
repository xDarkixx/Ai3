import hashlib
import os
import sqlite3
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")


def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def now():
    return datetime.now(timezone.utc).isoformat()


def install(app: FastAPI):
    from app.main import require_admin

    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS runtime_limits (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT OR IGNORE INTO runtime_limits(name,value,updated_at) VALUES('rate_limit_rpm',0,datetime('now'));
        INSERT OR IGNORE INTO runtime_limits(name,value,updated_at) VALUES('daily_request_limit',0,datetime('now'));
        INSERT OR IGNORE INTO runtime_limits(name,value,updated_at) VALUES('max_input_tokens',0,datetime('now'));
        INSERT OR IGNORE INTO runtime_limits(name,value,updated_at) VALUES('max_output_tokens',0,datetime('now'));
        INSERT OR IGNORE INTO runtime_limits(name,value,updated_at) VALUES('max_concurrent_requests',0,datetime('now'));
        """)

    class LimitsUpdate(BaseModel):
        rate_limit_rpm: int = Field(ge=0, le=1000000)
        daily_request_limit: int = Field(ge=0, le=100000000)
        max_input_tokens: int = Field(ge=0, le=100000000)
        max_output_tokens: int = Field(ge=0, le=100000000)
        max_concurrent_requests: int = Field(ge=0, le=100000)

    @app.get("/v1/admin/limits", dependencies=[Depends(require_admin)])
    def get_limits():
        with db() as con:
            rows = con.execute("SELECT name,value FROM runtime_limits").fetchall()
        values = {r["name"]: r["value"] for r in rows}
        return {
            "limits": values,
            "unlimited_value": 0,
            "description": "0 bedeutet unbegrenzt.",
        }

    @app.put("/v1/admin/limits", dependencies=[Depends(require_admin)])
    def set_limits(body: LimitsUpdate):
        with db() as con:
            for name, value in body.model_dump().items():
                con.execute(
                    "INSERT INTO runtime_limits(name,value,updated_at) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                    (name, value, now()),
                )
        return {"ok": True, "limits": body.model_dump(), "unlimited_value": 0}

    @app.post("/v1/admin/limits/unlimited", dependencies=[Depends(require_admin)])
    def set_unlimited():
        with db() as con:
            for name in ("rate_limit_rpm", "daily_request_limit", "max_input_tokens", "max_output_tokens", "max_concurrent_requests"):
                con.execute("UPDATE runtime_limits SET value=0,updated_at=? WHERE name=?", (now(), name))
        return {"ok": True, "message": "Alle AI3-Limits sind auf unbegrenzt gesetzt.", "unlimited_value": 0}

    @app.get("/v1/admin/branding", dependencies=[Depends(require_admin)])
    def branding():
        return {
            "product": "AI3",
            "brand": "xDarkixx",
            "copyright": "© 2026 xDarkixx — AI3",
            "software": "AI3 Universal AI Gateway",
            "notice": "Selbst gehostete Software. Betreiber ist für Konfiguration, Sicherheit, Datenschutz und rechtliche Anforderungen der eigenen Installation verantwortlich.",
        }

    return app
