import hashlib
import os
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
RATE_LIMIT_RPM = int(os.getenv("AI3_RATE_LIMIT_RPM", "0"))
DAILY_REQUEST_LIMIT = int(os.getenv("AI3_DAILY_REQUEST_LIMIT", "0"))
_windows: dict[str, deque[float]] = defaultdict(deque)


def _runtime_limits(principal_id=None):
    values = {"rate_limit_rpm": RATE_LIMIT_RPM, "daily_request_limit": DAILY_REQUEST_LIMIT}
    try:
        con = sqlite3.connect(DB_PATH)
        try:
            rows = con.execute("SELECT name,value FROM runtime_limits WHERE name IN ('rate_limit_rpm','daily_request_limit')").fetchall()
            values.update({str(k): int(v) for k, v in rows})
            if principal_id is not None:
                row = con.execute("SELECT rate_limit_rpm,daily_request_limit FROM principal_limits WHERE principal_id=?", (principal_id,)).fetchone()
                if row:
                    values["rate_limit_rpm"], values["daily_request_limit"] = int(row[0]), int(row[1])
        finally:
            con.close()
    except Exception:
        pass
    return values


def _token_principal(raw_token: str):
    if not raw_token:
        return None
    try:
        con = sqlite3.connect(DB_PATH)
        try:
            row = con.execute("SELECT principal_id FROM tokens WHERE token_hash=? AND active=1", (hashlib.sha256(raw_token.encode()).hexdigest(),)).fetchone()
            return int(row[0]) if row else None
        finally:
            con.close()
    except Exception:
        return None


def _daily_count(raw_token: str) -> int:
    if not raw_token:
        return 0
    try:
        con = sqlite3.connect(DB_PATH)
        try:
            since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            row = con.execute("SELECT COUNT(*) FROM usage_events WHERE principal_id=(SELECT principal_id FROM tokens WHERE token_hash=?) AND created_at>=?", (token_hash, since)).fetchone()
            return int(row[0] if row else 0)
        finally:
            con.close()
    except Exception:
        return 0


def install(app: FastAPI):
    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)
        authorization = request.headers.get("authorization", "")
        raw_token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
        principal_id = _token_principal(raw_token)
        limits = _runtime_limits(principal_id)
        rpm, daily = limits["rate_limit_rpm"], limits["daily_request_limit"]
        identity = raw_token or (request.client.host if request.client else "anonymous")
        bucket = _windows[identity[:256]]
        cutoff = time.monotonic() - 60
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if rpm > 0 and len(bucket) >= rpm:
            return JSONResponse({"error": {"message": "rate limit exceeded", "type": "rate_limit_error"}}, status_code=429, headers={"Retry-After": "60"})
        if raw_token and daily > 0 and _daily_count(raw_token) >= daily:
            return JSONResponse({"error": {"message": "daily request quota exceeded", "type": "quota_error"}}, status_code=429, headers={"Retry-After": "3600"})
        bucket.append(time.monotonic())
        return await call_next(request)
    return app
