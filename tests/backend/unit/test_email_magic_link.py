"""Regression tests for magic-link delivery semantics (HIGH-1).

With no mail transport configured, send_magic_link must report success in dev/test
(the console-printed link IS the delivery) but failure in production (so /auth/send-link
honestly returns 502 instead of telling the user a mail was sent).
"""
from app.config import settings
from app.services import email as email_service


def _clear_transports(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_password", "")
    monkeypatch.setattr(settings, "resend_api_key", "")


def test_send_magic_link_dev_no_transport_returns_true(monkeypatch):
    _clear_transports(monkeypatch)
    monkeypatch.setattr(settings, "app_env", "development")
    assert email_service.send_magic_link("dev@example.com", "tok") is True


def test_send_magic_link_test_env_no_transport_returns_true(monkeypatch):
    _clear_transports(monkeypatch)
    monkeypatch.setattr(settings, "app_env", "test")
    assert email_service.send_magic_link("t@example.com", "tok") is True


def test_send_magic_link_production_no_transport_returns_false(monkeypatch):
    _clear_transports(monkeypatch)
    monkeypatch.setattr(settings, "app_env", "production")
    assert email_service.send_magic_link("prod@example.com", "tok") is False


def test_send_magic_link_smtp_success_returns_true(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_user", "user")
    monkeypatch.setattr(settings, "smtp_password", "pass")
    monkeypatch.setattr(settings, "app_env", "production")
    sent = {}
    monkeypatch.setattr(
        email_service, "_send_via_smtp",
        lambda to, subj, html: sent.update(to=to),
    )
    assert email_service.send_magic_link("p@example.com", "tok") is True
    assert sent["to"] == "p@example.com"


def test_send_magic_link_smtp_failure_falls_through_to_false_in_prod(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_user", "user")
    monkeypatch.setattr(settings, "smtp_password", "pass")
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "app_env", "production")

    def _boom(*a, **k):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(email_service, "_send_via_smtp", _boom)
    assert email_service.send_magic_link("p@example.com", "tok") is False
