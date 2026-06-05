import pytest

from app.repositories import topic_repo, user_repo
from app.routers.chat import _build_topic_context
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_build_topic_context_includes_topic_title(db):
    user = await user_repo.create_user(
        db,
        UserCreate(email="topic-guard@example.com", display_name="TopicGuard"),
    )
    topic = await topic_repo.start_topic(
        db,
        TopicStart(user_id=user.id, name="Java Garbage Collector"),
    )

    ctx = await _build_topic_context(db, user.id, topic.id)

    assert "Java Garbage Collector" in ctx
    assert "ТЕКУЩАЯ ТЕМА" in ctx
    assert 'данный чат предназначен для изучения' in ctx
