import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    fd, path = tempfile.mkstemp(prefix="ai3-test-", suffix=".db")
    os.close(fd)
    from app import main

    monkeypatch.setattr(main, "DB_PATH", path)
    monkeypatch.setattr(main, "ADMIN_KEY", "test-admin-key")
    monkeypatch.setattr(main, "INITIAL_ADMIN_PASSWORD", "")
    main.init_db()
    with TestClient(main.app) as test_client:
        yield test_client, main
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def test_password_hash_is_not_plaintext(client):
    _, main = client
    encoded = main.hash_password("A-very-strong-test-password!")
    assert encoded.startswith("scrypt$")
    assert "A-very-strong-test-password!" not in encoded
    assert main.verify_password("A-very-strong-test-password!", encoded)
    assert not main.verify_password("wrong-password", encoded)


def test_principal_token_is_scoped_and_revoke_works(client):
    api, main = client
    headers = {"X-AI3-Admin-Key": "test-admin-key"}

    first = api.post("/v1/principals", json={"name": "alice", "kind": "user"}, headers=headers)
    second = api.post("/v1/principals", json={"name": "bob", "kind": "user"}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200

    token_a = api.post(
        "/v1/tokens",
        json={"principal": "alice", "name": "alice-client", "scopes": ["ai:inference"]},
        headers=headers,
    ).json()
    token_b = api.post(
        "/v1/tokens",
        json={"principal": "bob", "name": "bob-client", "scopes": ["ai:inference"]},
        headers=headers,
    ).json()

    assert token_a["token"] != token_b["token"]
    assert token_a["principal"] == "alice"
    assert token_b["principal"] == "bob"

    auth_a = api.get("/v1/agents", headers={"Authorization": f"Bearer {token_a['token']}"})
    assert auth_a.status_code == 403  # token has no agents:read scope

    revoked = api.post(
        "/v1/tokens/revoke",
        params={"token_prefix": token_a["token_prefix"]},
        headers=headers,
    )
    assert revoked.status_code == 200
    rejected = api.get("/v1/agents", headers={"Authorization": f"Bearer {token_a['token']}"})
    assert rejected.status_code == 401


def test_health_and_openai_compatible_surface(client):
    api, _ = client
    health = api.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "ai3-gateway"

    models = api.get("/v1/models")
    assert models.status_code in (200, 401, 503)


def test_runtime_limits_support_unlimited_zero(client):
    api, _ = client
    headers = {"X-AI3-Admin-Key": "test-admin-key"}
    response = api.get("/v1/admin/limits", headers=headers)
    assert response.status_code == 200
    assert response.json()["unlimited_value"] == 0
