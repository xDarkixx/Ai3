import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RUNTIME = Path("/runtime")
DB = Path(os.getenv("AI3_DB", "/data/ai3.db"))
ADMIN_KEY = os.getenv("AI3_ADMIN_KEY", "")
PREFIX = "ai3_admin_"


def now():
    return datetime.now(timezone.utc).isoformat()


def h(value):
    return hashlib.sha256(value.encode()).hexdigest()


def authorized(headers):
    key = headers.get("X-AI3-Admin-Key", "")
    if ADMIN_KEY and key and secrets.compare_digest(key, ADMIN_KEY):
        return True
    session = headers.get("X-AI3-Admin-Session", "")
    if not session.startswith(PREFIX) or not DB.exists():
        return False
    try:
        with sqlite3.connect(DB) as con:
            row = con.execute("SELECT expires_at FROM admin_sessions WHERE token_hash=? AND active=1", (h(session),)).fetchone()
        return bool(row and row[0] > now())
    except Exception:
        return False


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        return

    def send_json(self, code, data):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not authorized(self.headers):
            return self.send_json(401, {"detail": "invalid admin credentials"})
        if self.path == "/status":
            status = read_json(RUNTIME / "update-status.json", {"state": "unknown", "message": "Noch kein Update-Check ausgeführt."})
            config = read_json(RUNTIME / "update-config.json", {"auto_update": False})
            return self.send_json(200, {**status, "auto_update": bool(config.get("auto_update", False))})
        self.send_json(404, {"detail": "not found"})

    def do_POST(self):
        if not authorized(self.headers):
            return self.send_json(401, {"detail": "invalid admin credentials"})
        if self.path == "/check":
            (RUNTIME / "update-request").write_text("check\n", encoding="utf-8")
            return self.send_json(202, {"ok": True, "message": "Update-Check angefordert."})
        if self.path == "/update":
            (RUNTIME / "update-request").write_text("update\n", encoding="utf-8")
            return self.send_json(202, {"ok": True, "message": "Update angefordert. Der Host-Timer führt es aus."})
        if self.path == "/config":
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            write_json(RUNTIME / "update-config.json", {"auto_update": bool(body.get("auto_update", False)), "updated_at": now()})
            return self.send_json(200, {"ok": True, "auto_update": bool(body.get("auto_update", False))})
        self.send_json(404, {"detail": "not found"})


if __name__ == "__main__":
    RUNTIME.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", 8091), Handler).serve_forever()
