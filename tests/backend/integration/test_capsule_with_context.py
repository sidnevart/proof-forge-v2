"""
Integration tests for capsule generation with chat context.
"""
import pytest

from app.models.topic_material import TopicMaterial
from app.repositories import topic_repo, user_repo
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate


async def _make_user(db, email: str, name: str = "Test"):
    return await user_repo.create_user(db, UserCreate(email=email, display_name=name))


async def _make_topic(db, user_id: str, name: str = "Python asyncio"):
    return await topic_repo.start_topic(db, TopicStart(user_id=user_id, name=name))


async def _add_text_material(db, topic_id: str, user_id: str, content: str, name: str = "Material"):
    m = TopicMaterial(
        topic_id=topic_id, user_id=user_id, type="text",
        name=name, content_text=content,
    )
    db.add(m)
    await db.commit()
    return m


@pytest.mark.asyncio
async def test_capsule_generation_with_chat_messages(client, db):
    """POST /capsule/generate with chat_messages includes context in prompt."""
    user = await _make_user(db, "capsule-ctx@flow.test")
    uid = user.id
    topic = await _make_topic(db, uid, "Java GC")
    tid = topic.id

    await _add_text_material(
        db, tid, uid,
        content="Garbage Collector in Java manages heap memory automatically.",
        name="GC overview",
    )

    chat_messages = [
        {"role": "user", "content": "What is a memory leak in Java?"},
        {"role": "assistant", "content": "A memory leak happens when objects are no longer needed but still referenced, preventing GC from reclaiming them."},
    ]

    r = await client.post(
        f"/api/topics/{tid}/capsule/generate",
        json={"user_id": uid, "chat_messages": chat_messages},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["topic_id"] == tid
    assert body["status"] == "generating"
    assert body["capsule_id"]
