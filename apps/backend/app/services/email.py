import resend
from app.config import settings


def send_magic_link(email: str, token: str, display_name: str = "") -> bool:
    if not settings.resend_api_key:
        print(f"[DEV] Magic link for {email}: {settings.frontend_url}/auth/verify?token={token}")
        return True

    resend.api_key = settings.resend_api_key
    name = display_name or email.split("@")[0]
    link = f"{settings.frontend_url}/auth/verify?token={token}"

    resend.Emails.send({
        "from": settings.from_email,
        "to": [email],
        "subject": "Войди в Grasp",
        "html": f"""
        <div style="font-family: 'Manrope', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #131210; color: #efe9da; border-radius: 12px;">
            <h1 style="font-size: 24px; margin-bottom: 8px;">Привет, {name}!</h1>
            <p style="color: #968f7f; margin-bottom: 32px;">Нажми кнопку ниже, чтобы войти в Grasp. Ссылка действительна 10 минут.</p>
            <a href="{link}" style="display: inline-block; background: #3DDC91; color: #131210; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
                Войти в Grasp →
            </a>
            <p style="margin-top: 32px; color: #968f7f; font-size: 13px;">Если ты не запрашивал вход — просто игнорируй это письмо.</p>
        </div>
        """,
    })
    return True
