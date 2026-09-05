import os

from fastapi.testclient import TestClient

os.environ["AI3_DB"] = "/tmp/ai3_test.db"
os.environ["AI3_ADMIN_KEY"] = "test-admin-key"
os.environ.pop("AI3_LLM_BASE_URL", None)

try:
    os.remove(os.environ["AI3_DB"])
except FileNotFoundError:
    pass

from app.main import app  # noqa: E402


def test_health_and_web_ui():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["llm_configured"] is False

        web = client.get("/")
        assert web.status_code == 200
        assert "AI3 Control Center" in web.text
        assert client.get("/web/style.css").status_code == 200
        assert client.get("/web/app.js").status_code == 200


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

        admin_principals = client.get("/v1/admin/principals", headers=admin)
        assert admin_principals.status_code == 200
        assert any(x["name"] == "test-agent" for x in admin_principals.json())

        admin_tokens = client.get("/v1/admin/tokens", headers=admin)
        assert admin_tokens.status_code == 200
        assert admin_tokens.json()[0]["prefix"] == issued.json()["token_prefix"]
        assert "token" not in admin_tokens.json()[0]

        me = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["principal"] == "test-agent"

        agents = client.get("/v1/agents", headers={"Authorization": f"Bearer {token}"})
        assert agents.status_code == 200

        models = client.get("/v1/models", headers={"Authorization": f"Bearer {token}"})
        assert models.status_code == 503
        assert "AI3_LLM_BASE_URL" in models.json()["detail"]

        chat = client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": "local", "messages": [{"role": "user", "content": "Hallo"}]},
        )
        assert chat.status_code == 503

        prefix = issued.json()["token_prefix"]
        revoked = client.post(f"/v1/tokens/revoke?token_prefix={prefix}", headers=admin)
        assert revoked.status_code == 200

        rejected = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert rejected.status_code == 401


def test_ai_endpoints_require_bearer_token():
    with TestClient(app) as client:
        assert client.get("/v1/models").status_code == 401
        assert client.post("/v1/chat/completions", json={}).status_code == 401
        assert client.post("/v1/responses", json={}).status_code == 401
        assert client.post("/v1/embeddings", json={}).status_code == 401


def test_admin_endpoint_rejects_bad_key():
    with TestClient(app) as client:
        response = client.post(
            "/v1/principals",
            headers={"X-AI3-Admin-Key": "wrong"},
            json={"name": "blocked", "kind": "agent"},
        )
        assert response.status_code == 401
