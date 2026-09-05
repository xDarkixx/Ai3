import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

RATE_LIMIT_RPM = int(os.getenv("AI3_RATE_LIMIT_RPM", "120"))
DAILY_REQUEST_LIMIT = int(os.getenv("AI3_DAILY_REQUEST_LIMIT", "0"))

_windows: dict[str, deque[float]] = defaultdict(deque)


def install(app: FastAPI):
    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if RATE_LIMIT_RPM <= 0 or not request.url.path.startswith("/v1/"):
            return await call_next(request)
        authorization = request.headers.get("authorization", "")
        identity = authorization[7:].strip() if authorization.lower().startswith("bearer ") else request.client.host if request.client else "anonymous"
        key = identity[:256]
        now = time.monotonic()
        bucket = _windows[key]
        cutoff = now - 60
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_RPM:
            return JSONResponse({"error": {"message": "rate limit exceeded", "type": "rate_limit_error"}}, status_code=429, headers={"Retry-After": "60"})
        bucket.append(now)
        return await call_next(request)

    return app
