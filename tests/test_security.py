import os

from fastapi.testclient import TestClient

os.environ["AI3_DB"] = "/tmp/ai3_test.db"
os.environ["AI3_ADMIN_KEY"] = "test-admin-key"
os.environ.pop("AI3_LLM_BASE_URL", None)
os.environ["AI3_OLLAMA_URL"] = "http://127.0.0.1:9"

from app.main import app  # noqa: E402


def admin():
    return {"X-AI3-Admin-Key": "test-admin-key"}


def test_admin_password_session_and_security():
    with TestClient(app) as client:
        changed = client.post(
            "/v1/admin/password",
            headers=admin(),
            json={"current_password": None, "new_password": "TestPassword-1234"},
        )
        assert changed.status_code == 200

        login = client.post("/v1/admin/login", json={"password": "TestPassword-1234"})
        assert login.status_code == 200
        session = login.json()["session"]
        assert session.startswith("ai3_admin_")

        security = client.get("/v1/admin/security", headers={"X-AI3-Admin-Session": session})
        assert security.status_code == 200
        assert security.json()["password_configured"] is True
        assert security.json()["password_hash"] == "scrypt"

        rejected = client.get("/v1/admin/status", headers={"X-AI3-Admin-Session": "ai3_admin_invalid"})
        assert rejected.status_code == 401


def test_token_rotation():
    with TestClient(app) as client:
        principal = client.post(
            "/v1/principals",
            headers=admin(),
            json={"name": "rotation-agent", "kind": "agent"},
        )
        assert principal.status_code in (200, 409)
        issued = client.post(
            "/v1/tokens",
            headers=admin(),
            json={"principal": "rotation-agent", "name": "rotation", "scopes": ["ai:inference"]},
        )
        assert issued.status_code == 200
        old = issued.json()["token"]
        rotated = client.post(
            "/v1/tokens/rotate",
            headers=admin(),
            json={"token_prefix": issued.json()["token_prefix"]},
        )
        assert rotated.status_code == 200
        assert rotated.json()["token"] != old
        assert client.get("/v1/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
        assert client.get("/v1/me", headers={"Authorization": f"Bearer {rotated.json()['token']}"}).status_code == 200


def test_backend_discovery_is_admin_only():
    with TestClient(app) as client:
        public = client.get("/v1/admin/backends")
        assert public.status_code == 401
        result = client.get("/v1/admin/backends", headers=admin())
        assert result.status_code == 200
        names = {x["name"] for x in result.json()["backends"]}
        assert {"ollama", "vllm", "llamacpp", "openai-compatible"} <= names
