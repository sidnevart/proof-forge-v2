import pytest

from app.repositories import practice_repo, topic_repo, user_repo
from app.routers.chat import _build_topic_context
from app.schemas.practice import PracticeTaskCreate, StudySessionCreate
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_chat_returns_clear_error_when_llm_is_not_configured(client):
    res = await client.post(
        "/api/chat",
        json={"user_id": "user-no-llm", "message": "Привет", "history": []},
    )

    assert res.status_code == 503
    assert res.json()["detail"] == "LLM не настроен"


@pytest.mark.asyncio
async def test_chat_topic_context_includes_active_study_session_and_tasks(db):
    user = await user_repo.create_user(
        db,
        UserCreate(email="chat-context@example.com", display_name="ContextUser"),
    )
    topic = await topic_repo.start_topic(
        db,
        TopicStart(user_id=user.id, name="Kotlin coroutines"),
    )
    session = await practice_repo.create_study_session(
        db,
        StudySessionCreate(
            user_id=user.id,
            topic_id=topic.id,
            conspect_md="## Coroutine builders\nUse launch for fire-and-forget work.",
            learning_goals=["Explain launch vs async"],
        ),
    )
    await practice_repo.create_practice_task(
        db,
        PracticeTaskCreate(
            user_id=user.id,
            topic_id=topic.id,
            study_session_id=session.id,
            type="mini_project",
            title="Build a coroutine worker",
            instructions_md="Create a small worker that uses launch and async.",
            target_concepts=["launch", "async"],
            difficulty=2,
        ),
    )

    context = await _build_topic_context(db, user.id, topic.id)

    assert "Текущая учебная сессия" in context
    assert "Coroutine builders" in context
    assert "Build a coroutine worker" in context
    assert "launch" in context


@pytest.mark.asyncio
async def test_create_chat_session_and_list_messages(client, db):
    user = await user_repo.create_user(db, UserCreate(email="chat@example.com", display_name="ChatUser"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Rust lifetimes"))

    # Create chat session
    res = await client.post(
        "/api/chat/sessions",
        json={"user_id": user.id, "topic_id": topic.id, "title": "Rust session"},
    )
    assert res.status_code == 201
    session = res.json()
    assert session["user_id"] == user.id
    assert session["topic_id"] == topic.id
    assert session["title"] == "Rust session"
    assert session["status"] == "active"

    # List sessions
    listed = await client.get(f"/api/chat/sessions?user_id={user.id}")
    assert listed.status_code == 200
    sessions = listed.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] == session["id"]

    # Create messages
    msg1 = await client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"role": "user", "content": "What are lifetimes?"},
    )
    assert msg1.status_code == 201
    assert msg1.json()["role"] == "user"

    msg2 = await client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"role": "assistant", "content": "Lifetimes ensure references are valid."},
    )
    assert msg2.status_code == 201

    # List messages
    messages = await client.get(f"/api/chat/sessions/{session['id']}/messages")
    assert messages.status_code == 200
    msgs = messages.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_chat_session_with_study_session_link(client, db):
    user = await user_repo.create_user(db, UserCreate(email="chat-link@example.com", display_name="LinkUser"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Go channels"))

    study = await client.post(
        "/api/study-sessions",
        json={"user_id": user.id, "topic_id": topic.id},
    )
    study_session_id = study.json()["session"]["id"]

    res = await client.post(
        "/api/chat/sessions",
        json={
            "user_id": user.id,
            "topic_id": topic.id,
            "title": "Go channels chat",
            "study_session_id": study_session_id,
        },
    )
    assert res.status_code == 201
    assert res.json()["study_session_id"] == study_session_id


@pytest.mark.asyncio
async def test_list_chat_sessions_ordered_by_updated_at(client, db):
    user = await user_repo.create_user(db, UserCreate(email="chat-order@example.com", display_name="OrderUser"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Scala"))

    # Create two sessions
    s1 = await client.post(
        "/api/chat/sessions",
        json={"user_id": user.id, "topic_id": topic.id, "title": "First"},
    )
    s2 = await client.post(
        "/api/chat/sessions",
        json={"user_id": user.id, "topic_id": topic.id, "title": "Second"},
    )

    listed = await client.get(f"/api/chat/sessions?user_id={user.id}")
    sessions = listed.json()
    assert len(sessions) == 2
    # Most recently updated first
    assert sessions[0]["id"] == s2.json()["id"]
    assert sessions[1]["id"] == s1.json()["id"]
