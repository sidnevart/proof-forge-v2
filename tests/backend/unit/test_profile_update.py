import pytest
from app.repositories import user_repo
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_create_user_creates_profile(db):
    user = await user_repo.create_user(db, UserCreate(email="test@example.com", display_name="Test"))
    profile = await user_repo.get_profile(db, user.id)

    assert profile is not None
    assert profile.user_id == user.id
    assert profile.skill_level == "beginner"
    assert profile.known_topics == []
    assert profile.weak_spots == []


@pytest.mark.asyncio
async def test_profile_not_found_for_unknown_user(db):
    profile = await user_repo.get_profile(db, "nonexistent-user-id")
    assert profile is None
