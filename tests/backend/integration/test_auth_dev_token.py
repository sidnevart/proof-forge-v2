import pytest

from app.routers import auth as auth_router
from app.services import jwt as jwt_service


@pytest.mark.asyncio
async def test_dev_token_creates_user_and_returns_valid_token(client):
    res = await client.post(
        "/api/auth/dev-token",
        json={"email": "e2e-user@example.com", "display_name": "E2E User"},
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["email"] == "e2e-user@example.com"
    assert body["user_id"]
    assert body["access_token"]

    payload = jwt_service.decode_token(body["access_token"])
    assert payload is not None
    assert payload["sub"] == body["user_id"]
    assert payload["email"] == "e2e-user@example.com"


@pytest.mark.asyncio
async def test_dev_token_is_idempotent_for_same_email(client):
    first = await client.post(
        "/api/auth/dev-token",
        json={"email": "e2e-repeat@example.com", "display_name": "Repeat"},
    )
    second = await client.post(
        "/api/auth/dev-token",
        json={"email": "e2e-repeat@example.com", "display_name": "Repeat"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["user_id"] == second.json()["user_id"]


@pytest.mark.asyncio
async def test_dev_token_disabled_in_production(client, monkeypatch):
    monkeypatch.setattr(auth_router.settings, "app_env", "production")

    res = await client.post(
        "/api/auth/dev-token",
        json={"email": "prod-block@example.com", "display_name": "Blocked"},
    )

    assert res.status_code == 404
