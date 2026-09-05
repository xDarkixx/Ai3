"""Encrypted chat history for AI3.

Chat payloads are encrypted with AES-256-GCM before they are written to SQLite.
The encryption key is deliberately kept outside the database.
"""

import base64
import binascii
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
KEY_FILE = os.getenv("AI3_DATA_ENCRYPTION_KEY_FILE", "")
KEY_ENV = os.getenv("AI3_DATA_ENCRYPTION_KEY", "")
MAX_CHAT_BYTES = int(os.getenv("AI3_MAX_CHAT_STORAGE_BYTES", "2000000"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_key() -> bytes:
    value = ""
    if KEY_FILE:
        try:
            with open(KEY_FILE, "r", encoding="utf-8") as handle:
                value = handle.read().strip()
        except OSError as exc:
            raise RuntimeError(f"AI3 data encryption key file unavailable: {exc}") from exc
    elif KEY_ENV:
        value = KEY_ENV.strip()
    else:
        raise RuntimeError("AI3_DATA_ENCRYPTION_KEY_FILE or AI3_DATA_ENCRYPTION_KEY is required")

    try:
        if len(value) == 64:
            key = bytes.fromhex(value)
        else:
            key = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("AI3 data encryption key must be 32 bytes as hex or base64") from exc
    if len(key) != 32:
        raise RuntimeError("AI3 data encryption key must be exactly 32 bytes")
    return key


def encrypt_json(payload: object, *, principal_id: int, conversation_id: str) -> tuple[bytes, bytes]:
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(plaintext) > MAX_CHAT_BYTES:
        raise ValueError("chat payload exceeds storage limit")
    nonce = secrets.token_bytes(12)
    aad = f"ai3-chat-v1:{principal_id}:{conversation_id}".encode("utf-8")
    ciphertext = AESGCM(_load_key()).encrypt(nonce, plaintext, aad)
    return nonce, ciphertext


def decrypt_json(nonce: bytes, ciphertext: bytes, *, principal_id: int, conversation_id: str):
    aad = f"ai3-chat-v1:{principal_id}:{conversation_id}".encode("utf-8")
    plaintext = AESGCM(_load_key()).decrypt(nonce, ciphertext, aad)
    return json.loads(plaintext.decode("utf-8"))


def init_chat_db() -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS encrypted_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                principal_id INTEGER NOT NULL,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_chat_principal ON encrypted_chat_messages(principal_id, created_at)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversation ON encrypted_chat_messages(principal_id, conversation_id, id)")


def _principal(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    try:
        from app.main import get_principal
        return get_principal(token)
    except Exception:
        return None


def _capture_route(app):
    for route in app.routes:
        if getattr(route, "path", None) != "/v1/chat/completions" or getattr(route, "methods", set()) != {"POST"}:
            continue
        if getattr(route, "_ai3_encrypted_chat_wrapped", False):
            return
        original = route.dependant.call

        async def wrapped(request: Request, row, _original=original):
            principal = row or _principal(request)
            response = await _original(request=request, row=principal)
            if not principal:
                return response
            try:
                raw = await request.body()
                if len(raw) > MAX_CHAT_BYTES:
                    return JSONResponse({"error": {"message": "chat body too large", "type": "invalid_request_error"}}, status_code=413)
                payload = json.loads(raw or b"{}")
                if payload.get("stream") is True:
                    return response
                body = getattr(response, "body", None)
                if not body:
                    return response
                result = json.loads(body)
                messages = payload.get("messages")
                choices = result.get("choices", []) if isinstance(result, dict) else []
                assistant = choices[0].get("message") if choices and isinstance(choices[0], dict) else None
                if not messages or not assistant:
                    return response
                conversation_id = request.headers.get("x-ai3-conversation-id") or secrets.token_urlsafe(18)
                record = {"request": {"messages": messages}, "response": assistant}
                nonce, ciphertext = encrypt_json(record, principal_id=int(principal["principal_id"]), conversation_id=conversation_id)
                with sqlite3.connect(DB_PATH) as con:
                    con.execute("INSERT INTO encrypted_chat_messages(conversation_id,principal_id,nonce,ciphertext,created_at) VALUES(?,?,?,?,?)", (conversation_id, int(principal["principal_id"]), nonce, ciphertext, _now()))
                response.headers["X-AI3-Conversation-ID"] = conversation_id
            except Exception:
                # Chat inference must continue even if history storage fails.
                pass
            return response

        route.dependant.call = wrapped
        route._ai3_encrypted_chat_wrapped = True
        return


def install(app):
    init_chat_db()
    _capture_route(app)

    @app.get("/v1/chat/history")
    async def chat_history(request: Request):
        principal = _principal(request)
        if not principal:
            raise HTTPException(401, "Bearer token required")
        with sqlite3.connect(DB_PATH) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("SELECT id,conversation_id,nonce,ciphertext,created_at FROM encrypted_chat_messages WHERE principal_id=? ORDER BY id DESC LIMIT 200", (int(principal["principal_id"]),)).fetchall()
        result = []
        for row in reversed(rows):
            try:
                data = decrypt_json(row["nonce"], row["ciphertext"], principal_id=int(principal["principal_id"]), conversation_id=row["conversation_id"])
                result.append({"id": row["id"], "conversation_id": row["conversation_id"], "created_at": row["created_at"], "data": data})
            except Exception:
                result.append({"id": row["id"], "conversation_id": row["conversation_id"], "created_at": row["created_at"], "data": None, "error": "history entry could not be decrypted"})
        return {"encrypted_at_rest": True, "count": len(result), "messages": result}

    @app.delete("/v1/chat/history")
    async def delete_chat_history(request: Request):
        principal = _principal(request)
        if not principal:
            raise HTTPException(401, "Bearer token required")
        with sqlite3.connect(DB_PATH) as con:
            cur = con.execute("DELETE FROM encrypted_chat_messages WHERE principal_id=?", (int(principal["principal_id"]),))
        return {"ok": True, "deleted": cur.rowcount}

    @app.get("/v1/admin/chat-security")
    async def chat_security_status(request: Request):
        principal = _principal(request)
        if not principal:
            raise HTTPException(401, "Bearer token required")
        return {"encrypted_at_rest": True, "algorithm": "AES-256-GCM", "key_location": "external-secret", "plaintext_chat_storage": False}

    return app
