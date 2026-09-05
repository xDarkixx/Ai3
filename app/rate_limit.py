import hashlib
import os
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

DB_PATH = os.getenv("AI3_DB", "/data/ai3.db")
RATE_LIMIT_RPM = int(os.getenv("AI3_RATE_LIMIT_RPM", "120"))
DAILY_REQUEST_LIMIT = int(os.getenv("AI3_DAILY_REQUEST_LIMIT", "0"))

_windows: dict[str, deque[float]] = defaultdict(deque)


def _daily_count(raw_token: str) -> int:
    if DAILY_REQUEST_LIMIT <= 0 or not raw_token:
        return 0
    try:
        con = sqlite3.connect(DB_PATH)
        try:
            since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            row = con.execute(
                "SELECT COUNT(*) FROM usage_events WHERE principal_id=(SELECT principal_id FROM tokens WHERE token_hash=?) AND created_at>=?",
                (token_hash, since),
            ).fetchone()
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
        identity = raw_token or (request.client.host if request.client else "anonymous")
        key = identity[:256]
        now_mono = time.monotonic()
        bucket = _windows[key]
        cutoff = now_mono - 60
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if RATE_LIMIT_RPM > 0 and len(bucket) >= RATE_LIMIT_RPM:
            return JSONResponse({"error": {"message": "rate limit exceeded", "type": "rate_limit_error"}}, status_code=429, headers={"Retry-After": "60"})
        if raw_token and DAILY_REQUEST_LIMIT > 0 and _daily_count(raw_token) >= DAILY_REQUEST_LIMIT:
            return JSONResponse({"error": {"message": "daily request quota exceeded", "type": "quota_error"}}, status_code=429, headers={"Retry-After": "3600"})
        bucket.append(now_mono)
        return await call_next(request)

    return app
