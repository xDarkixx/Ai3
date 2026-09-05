"""Small application-layer DDoS/abuse mitigation for AI3.

This is intentionally bounded and dependency-free. It complements, but does not
replace, a firewall/reverse proxy/CDN for volumetric DDoS attacks.
"""

import os
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

IP_RPM = max(1, int(os.getenv("AI3_DDOS_IP_RPM", "120")))
MAX_BODY_BYTES = max(1024, int(os.getenv("AI3_MAX_REQUEST_BYTES", "2000000")))
MAX_CONCURRENT_PER_IP = max(1, int(os.getenv("AI3_DDOS_MAX_CONCURRENT_PER_IP", "20")))
WINDOW_SECONDS = 60.0

_windows: dict[str, deque[float]] = defaultdict(deque)
_active: dict[str, int] = defaultdict(int)
_last_seen: dict[str, float] = {}


def _client_ip(request: Request) -> str:
    # Do not trust X-Forwarded-For by default; the proxy should be configured to
    # overwrite it before AI3 is placed behind a trusted reverse proxy.
    return (request.client.host if request.client else "unknown")[:128]


def _cleanup(now: float) -> None:
    if len(_windows) < 4096:
        return
    stale = [key for key, seen in _last_seen.items() if now - seen > 300]
    for key in stale:
        _windows.pop(key, None)
        _active.pop(key, None)
        _last_seen.pop(key, None)


def install(app):
    @app.middleware("http")
    async def ddos_guard(request: Request, call_next):
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)

        now = time.monotonic()
        ip = _client_ip(request)
        _last_seen[ip] = now
        _cleanup(now)

        bucket = _windows[ip]
        cutoff = now - WINDOW_SECONDS
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= IP_RPM:
            return JSONResponse(
                {"error": {"message": "request rate temporarily limited", "type": "ddos_protection"}},
                status_code=429,
                headers={"Retry-After": "60", "Cache-Control": "no-store"},
            )

        active = _active[ip]
        if active >= MAX_CONCURRENT_PER_IP:
            return JSONResponse(
                {"error": {"message": "too many concurrent requests", "type": "ddos_protection"}},
                status_code=429,
                headers={"Retry-After": "5", "Cache-Control": "no-store"},
            )

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_BODY_BYTES:
                    return JSONResponse({"error": {"message": "request body too large", "type": "request_too_large"}}, status_code=413)
            except ValueError:
                return JSONResponse({"error": {"message": "invalid content-length", "type": "invalid_request"}}, status_code=400)

        bucket.append(now)
        _active[ip] = active + 1
        try:
            return await call_next(request)
        finally:
            _active[ip] = max(0, _active[ip] - 1)

    return app
