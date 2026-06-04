import uuid
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.auth_token import AuthToken


async def create_token(db: AsyncSession, email: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    record = AuthToken(token=token, email=email, expires_at=expires_at)
    db.add(record)
    await db.commit()
    return token


async def consume_token(db: AsyncSession, token: str) -> str | None:
    """Verify token, mark as used, return email or None."""
    result = await db.execute(select(AuthToken).where(AuthToken.token == token))
    record = result.scalar_one_or_none()
    if not record:
        return None
    if record.used_at is not None:
        return None
    if datetime.now(timezone.utc) > record.expires_at:
        return None
    record.used_at = datetime.now(timezone.utc)
    await db.commit()
    return record.email
