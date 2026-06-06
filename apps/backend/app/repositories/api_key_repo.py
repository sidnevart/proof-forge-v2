"""API key CRUD and validation for IDE plugin authentication."""
import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_raw_key() -> str:
    """Return a new raw API key hex string. The caller shows this to the user once."""
    return secrets.token_hex(24)


async def create_key(db: AsyncSession, user_id: str, name: str = "") -> tuple[ApiKey, str]:
    """Persist a new key and return (model, raw_key). The raw key is NOT stored."""
    raw = generate_raw_key()
    key = ApiKey(user_id=user_id, key_hash=_hash(raw), name=name)
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key, raw


async def list_keys(db: AsyncSession, user_id: str) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_key(db: AsyncSession, key_id: str, user_id: str) -> bool:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    )
    key = result.scalar_one_or_none()
    if not key:
        return False
    await db.delete(key)
    await db.commit()
    return True


async def validate_key(db: AsyncSession, raw: str) -> str | None:
    """Return user_id if the raw key is valid, else None. Updates last_used_at."""
    kh = _hash(raw)
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == kh))
    key = result.scalar_one_or_none()
    if not key:
        return None
    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == key.id)
        .values(last_used_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return key.user_id
