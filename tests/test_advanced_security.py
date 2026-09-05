import os
from pathlib import Path

DB = "/tmp/ai3_advanced_security_test.db"
if os.path.exists(DB):
    os.remove(DB)
os.environ["AI3_DB"] = DB
os.environ["AI3_ADMIN_KEY"] = "test-admin-key"
os.environ["AI3_BACKUP_DIR"] = "/tmp/ai3-backups"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.advanced_security import install  # noqa: E402

install(app)


def admin():
    return {"X-AI3-Admin-Key": "test-admin-key"}


def test_oauth_client_credentials_and_refresh_rotation():
    with TestClient(app) as client:
        principal = client.post("/v1/principals", headers=admin(), json={"name": "oauth-agent", "kind": "agent"})
        assert principal.status_code in (200, 409)
        created = client.post(
            "/v1/admin/oauth/clients",
            headers=admin(),
            json={"name": "openclaw", "principal": "oauth-agent", "scopes": ["ai:inference"]},
        )
        assert created.status_code == 200
        data = created.json()
        issued = client.post(
            "/oauth/token",
            json={"grant_type": "client_credentials", "client_id": data["client_id"], "client_secret": data["client_secret"]},
        )
        assert issued.status_code == 200
        first = issued.json()
        assert first["access_token"].startswith("ai3_")
        assert first["refresh_token"].startswith("ai3_rt_")

        refreshed = client.post(
            "/oauth/token",
            json={"grant_type": "refresh_token", "client_id": data["client_id"], "client_secret": data["client_secret"], "refresh_token": first["refresh_token"]},
        )
        assert refreshed.status_code == 200
        second = refreshed.json()
        assert second["access_token"] != first["access_token"]
        assert second["refresh_token"] != first["refresh_token"]

        replay = client.post(
            "/oauth/token",
            json={"grant_type": "refresh_token", "client_id": data["client_id"], "client_secret": data["client_secret"], "refresh_token": first["refresh_token"]},
        )
        assert replay.status_code == 401


def test_admin_backup_creates_sqlite_snapshot():
    backup_dir = Path("/tmp/ai3-backups")
    if backup_dir.exists():
        for item in backup_dir.glob("ai3-*.db"):
            item.unlink()
    with TestClient(app) as client:
        response = client.post("/v1/admin/backup", headers=admin())
        assert response.status_code == 200
        path = Path(response.json()["file"])
        assert path.exists()
        assert path.stat().st_size > 0
        listed = client.get("/v1/admin/backups", headers=admin())
        assert listed.status_code == 200
        assert any(x["file"] == path.name for x in listed.json())
