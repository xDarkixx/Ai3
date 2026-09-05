"""Encrypted user profile storage for AI3.

Personal profile data such as address and phone number is encrypted at rest with
AI3's AES-256-GCM data key. Only the owning user session can read or update it.
"""

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.chat_security import decrypt_json, encrypt_json

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
USER_SESSION_PREFIX = "ai3_user_"


def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def now():
    return datetime.now(timezone.utc).isoformat()


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def install(app: FastAPI):
    with db() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS encrypted_user_profiles (
                user_id INTEGER PRIMARY KEY,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )

    class ProfileUpdate(BaseModel):
        first_name: str = Field(default="", max_length=100)
        last_name: str = Field(default="", max_length=100)
        street: str = Field(default="", max_length=160)
        house_number: str = Field(default="", max_length=30)
        postal_code: str = Field(default="", max_length=20)
        city: str = Field(default="", max_length=120)
        country: str = Field(default="Deutschland", max_length=80)
        phone: str = Field(default="", max_length=40)
        company: str = Field(default="", max_length=160)
        terms_accepted: bool = False

    def require_user(session: Optional[str] = Header(default=None)):
        if not session or not session.startswith(USER_SESSION_PREFIX):
            raise HTTPException(401, "user session required")
        with db() as con:
            row = con.execute(
                """SELECT u.*, p.name AS principal_name, p.active AS principal_active
                   FROM user_sessions s JOIN users u ON u.id=s.user_id
                   JOIN principals p ON p.id=u.principal_id
                   WHERE s.token_hash=? AND s.active=1""",
                (hash_value(session),),
            ).fetchone()
        if not row:
            raise HTTPException(401, "invalid user session")
        if row["expires_at"] <= now():
            with db() as con:
                con.execute("UPDATE user_sessions SET active=0 WHERE token_hash=?", (hash_value(session),))
            raise HTTPException(401, "user session expired")
        if not row["active"] or not row["principal_active"]:
            raise HTTPException(403, "user is inactive")
        return row

    @app.get("/v1/user/profile")
    def get_profile(session: Optional[str] = Header(default=None)):
        user = require_user(session)
        with db() as con:
            row = con.execute("SELECT nonce,ciphertext,updated_at FROM encrypted_user_profiles WHERE user_id=?", (user["id"],)).fetchone()
        if not row:
            return {"profile": {}, "encrypted_at_rest": True}
        try:
            profile = decrypt_json(row["nonce"], row["ciphertext"], principal_id=int(user["principal_id"]), conversation_id=f"profile:{user['id']}")
        except Exception as exc:
            raise HTTPException(500, "profile could not be decrypted") from exc
        return {"profile": profile, "encrypted_at_rest": True, "updated_at": row["updated_at"]}

    @app.put("/v1/user/profile")
    def update_profile(body: ProfileUpdate, session: Optional[str] = Header(default=None)):
        user = require_user(session)
        if not body.terms_accepted:
            raise HTTPException(422, "terms and privacy policy must be accepted")
        profile = body.model_dump()
        profile["updated_at"] = now()
        nonce, ciphertext = encrypt_json(profile, principal_id=int(user["principal_id"]), conversation_id=f"profile:{user['id']}")
        with db() as con:
            con.execute(
                """INSERT INTO encrypted_user_profiles(user_id,nonce,ciphertext,updated_at)
                   VALUES(?,?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET nonce=excluded.nonce,ciphertext=excluded.ciphertext,updated_at=excluded.updated_at""",
                (user["id"], nonce, ciphertext, now()),
            )
        return {"ok": True, "encrypted_at_rest": True, "message": "profile saved"}

    return app
