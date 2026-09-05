import os
from fastapi.testclient import TestClient

os.environ["AI3_DB"] = "/tmp/ai3_test.db"
os.environ["AI3_ADMIN_KEY"] = "test-admin-key"

try:
    os.remove(os.environ["AI3_DB"])
except FileNotFoundError:
    pass

from app.main import app  # noqa: E402


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_token_lifecycle():
    with TestClient(app) as client:
        admin = {"X-AI3-Admin-Key": "test-admin-key"}
        principal = client.post(
            "/v1/principals",
            headers=admin,
            json={"name": "test-agent", "kind": "agent"},
        )
        assert principal.status_code == 200

        issued = client.post(
            "/v1/tokens",
            headers=admin,
            json={
                "principal": "test-agent",
                "name": "test",
                "scopes": ["ai:inference", "agents:read"],
            },
        )
        assert issued.status_code == 200
        token = issued.json()["token"]
        assert token.startswith("ai3_")

        me = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["principal"] == "test-agent"

        agents = client.get("/v1/agents", headers={"Authorization": f"Bearer {token}"})
        assert agents.status_code == 200

        prefix = issued.json()["token_prefix"]
        revoked = client.post(f"/v1/tokens/revoke?token_prefix={prefix}", headers=admin)
        assert revoked.status_code == 200

        rejected = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert rejected.status_code == 401


def test_admin_endpoint_rejects_bad_key():
    with TestClient(app) as client:
        response = client.post(
            "/v1/principals",
            headers={"X-AI3-Admin-Key": "wrong"},
            json={"name": "blocked", "kind": "agent"},
        )
        assert response.status_code == 401
