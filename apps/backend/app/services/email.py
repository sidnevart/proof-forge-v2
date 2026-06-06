import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

from app.config import settings


def _render_html(name: str, link: str) -> str:
    return f"""
        <div style="font-family: 'Manrope', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #131210; color: #efe9da; border-radius: 12px;">
            <h1 style="font-size: 24px; margin-bottom: 8px;">Привет, {name}!</h1>
            <p style="color: #968f7f; margin-bottom: 32px;">Нажми кнопку ниже, чтобы войти в Grasp. Ссылка действительна 10 минут.</p>
            <a href="{link}" style="display: inline-block; background: #3DDC91; color: #131210; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
                Войти в Grasp →
            </a>
            <p style="margin-top: 32px; color: #968f7f; font-size: 13px;">Если ты не запрашивал вход — просто игнорируй это письмо.</p>
        </div>
    """


def _send_via_smtp(to_email: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("Grasp", settings.smtp_from or settings.smtp_user))
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    if settings.smtp_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)


def send_magic_link(email: str, token: str, display_name: str = "") -> bool:
    """Send the magic-link email. Returns True if delivered (or dev-printed),
    False if all delivery paths failed. The caller must never crash on a mail
    failure — a mail outage should not 500 the login request."""
    name = display_name or email.split("@")[0]
    link = f"{settings.frontend_url}/auth/verify?token={token}"
    html = _render_html(name, link)
    subject = "Войди в Grasp"

    # 1. SMTP (e.g. Gmail) — preferred, works without domain verification.
    if settings.smtp_host and settings.smtp_user and settings.smtp_password:
        try:
            _send_via_smtp(email, subject, html)
            return True
        except Exception as exc:  # noqa: BLE001 — never let mail failure 500 the endpoint
            print(f"[email] SMTP send failed for {email}: {exc!r}")

    # 2. Resend — fallback if configured.
    if settings.resend_api_key:
        try:
            import resend
            resend.api_key = settings.resend_api_key
            resend.Emails.send({
                "from": settings.from_email,
                "to": [email],
                "subject": subject,
                "html": html,
            })
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[email] Resend send failed for {email}: {exc!r}")

    # 3. Last-resort fallback: log the link so login is still possible in dev.
    print(f"[email] No working mail transport. Magic link for {email}: {link}")
    return False
