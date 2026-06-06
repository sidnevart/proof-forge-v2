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


@pytest.mark.asyncio
async def test_send_link_succeeds_in_dev_without_mail_transport(client, monkeypatch):
    """HIGH-1: with no SMTP/Resend configured, /send-link must return 200 in dev
    (the console-printed link is the delivery), not 502."""
    from app.services import email as email_service
    monkeypatch.setattr(email_service.settings, "app_env", "development")
    monkeypatch.setattr(email_service.settings, "smtp_host", "")
    monkeypatch.setattr(email_service.settings, "smtp_user", "")
    monkeypatch.setattr(email_service.settings, "smtp_password", "")
    monkeypatch.setattr(email_service.settings, "resend_api_key", "")

    res = await client.post(
        "/api/auth/send-link",
        json={"email": "login@example.com", "display_name": "Login"},
    )
    assert res.status_code == 200, res.text
    assert "message" in res.json()


@pytest.mark.asyncio
async def test_send_link_returns_502_in_production_without_transport(client, monkeypatch):
    """HIGH-1: in production a missing transport is a real failure → 502, not a
    misleading 'mail sent' 200."""
    from app.services import email as email_service
    monkeypatch.setattr(email_service.settings, "app_env", "production")
    monkeypatch.setattr(email_service.settings, "smtp_host", "")
    monkeypatch.setattr(email_service.settings, "smtp_user", "")
    monkeypatch.setattr(email_service.settings, "smtp_password", "")
    monkeypatch.setattr(email_service.settings, "resend_api_key", "")

    res = await client.post(
        "/api/auth/send-link",
        json={"email": "prod-login@example.com", "display_name": "ProdLogin"},
    )
    assert res.status_code == 502, res.text
