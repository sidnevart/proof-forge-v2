"""Integration tests for the onboarding endpoints + profile → session flow."""
import asyncio

import pytest

from app.repositories import topic_repo, user_repo
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate


async def _drain_session(client, session_id: str, timeout: float = 3.0) -> str:
    """Poll until background generation leaves 'generating' so the bg task finishes
    inside the test (avoids file-SQLite lock contention bleeding into the next test)."""
    deadline = asyncio.get_event_loop().time() + timeout
    status = "generating"
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.1)
        res = await client.get(f"/api/study-sessions/{session_id}")
        status = res.json().get("status", status)
        if status != "generating":
            break
    return status


@pytest.mark.asyncio
async def test_onboarding_questions_returns_slots(client, db):
    user = await user_repo.create_user(db, UserCreate(email="onb1@example.com", display_name="O"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Go channels"))

    res = await client.post(
        "/api/onboarding/questions",
        json={"user_id": user.id, "topic_id": topic.id},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["domain"] in ("coding", "language", "theory_math", "humanities", "general")
    ids = [s["id"] for s in body["slots"]]
    assert ids[0] == "goal"
    assert "task_format" in ids


@pytest.mark.asyncio
async def test_onboarding_plan_persists_profile(client, db):
    user = await user_repo.create_user(db, UserCreate(email="onb2@example.com", display_name="O"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Python async"))

    res = await client.post(
        "/api/onboarding/plan",
        json={
            "user_id": user.id,
            "topic_id": topic.id,
            "answers": {"goal": "interview", "focus": ["event loop"], "known": ["coroutines"]},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "plan_md" in body and body["plan_md"]
    assert body["study_profile"]["goal"] == "interview"
    assert body["study_profile"]["focus_subtopics"] == ["event loop"]

    # Persisted on the topic so chat + generation can read it.
    refreshed = await topic_repo.get_topic(db, topic.id)
    assert refreshed.strategy_config["focus_subtopics"] == ["event loop"]


@pytest.mark.asyncio
async def test_study_session_accepts_study_profile(client, db):
    user = await user_repo.create_user(db, UserCreate(email="onb3@example.com", display_name="O"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Rust ownership"))

    profile = {"goal": "understand", "focus_subtopics": ["borrow checker"], "depth": "moderate"}
    res = await client.post(
        "/api/study-sessions",
        json={"user_id": user.id, "topic_id": topic.id, "study_profile": profile},
    )
    assert res.status_code == 201

    refreshed = await topic_repo.get_topic(db, topic.id)
    assert refreshed.strategy_config["focus_subtopics"] == ["borrow checker"]
    await _drain_session(client, res.json()["session"]["id"])


@pytest.mark.asyncio
async def test_study_session_skip_uses_default(client, db):
    user = await user_repo.create_user(db, UserCreate(email="onb4@example.com", display_name="O"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="SQL joins"))

    # Skip path: no study_profile → balanced default; session still generates (fallback).
    res = await client.post(
        "/api/study-sessions",
        json={"user_id": user.id, "topic_id": topic.id, "study_profile": None},
    )
    assert res.status_code == 201
    assert res.json()["generation_status"] == "generating"
    await _drain_session(client, res.json()["session"]["id"])
