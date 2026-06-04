from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, LearnerProfile
from app.schemas.user import UserCreate


async def find_or_create(db: AsyncSession, email: str, display_name: str = "") -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(email=email, display_name=display_name or email.split("@")[0])
    db.add(user)
    await db.flush()
    profile = LearnerProfile(user_id=user.id, known_topics=[], weak_spots=[], skill_level="beginner")
    db.add(profile)
    await db.commit()
    await db.refresh(user)
    return user


async def find_or_create_with_flag(db: AsyncSession, email: str, display_name: str = "") -> tuple[bool, User]:
    """Returns (is_new, user). is_new=True means first login ever."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        return False, user
    user = User(email=email, display_name=display_name or email.split("@")[0])
    db.add(user)
    await db.flush()
    profile = LearnerProfile(user_id=user.id, known_topics=[], weak_spots=[], skill_level="beginner")
    db.add(profile)
    await db.commit()
    await db.refresh(user)
    return True, user


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(email=data.email, display_name=data.display_name)
    db.add(user)
    await db.flush()
    profile = LearnerProfile(user_id=user.id, known_topics=[], weak_spots=[], skill_level="beginner")
    db.add(profile)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_profile(db: AsyncSession, user_id: str) -> LearnerProfile | None:
    result = await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
    return result.scalar_one_or_none()
