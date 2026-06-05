"""
Integration tests covering the full user flows that were broken in production:
  - Dashboard endpoints (agent-context, cards/stats, study-sessions list)
  - Capsule generation flow
  - Study session flow
  - Cards flow
"""
import asyncio
import pytest
import pytest_asyncio

from app.models.topic_material import TopicMaterial
from app.repositories import topic_repo, user_repo
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate


# ── Helpers ───────────────────────────────────────────────────────────────────

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


async def _poll_capsule(client, capsule_id: str, timeout: float = 3.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.1)
        r = await client.get(f"/api/capsules/{capsule_id}")
        if r.status_code == 200 and r.json()["status"] != "generating":
            return r.json()
    return {}


async def _poll_tasks(client, user_id: str, session_id: str, timeout: float = 3.0) -> list:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.1)
        res = await client.get(f"/api/practice-tasks?user_id={user_id}&status=active")
        tasks = [t for t in res.json() if t["study_session_id"] == session_id]
        if tasks:
            return sorted(tasks, key=lambda t: t["created_at"])
    return []


# ── Dashboard flow ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_flow(client, db):
    """All endpoints hit on dashboard load return 200 for a registered user."""
    user = await _make_user(db, "dashboard@flow.test")
    uid = user.id

    # agent-context — web format (?user_id=)
    r = await client.get(f"/api/agent-context?user_id={uid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == uid
    assert "profile" in body and "capsules" in body

    # agent-context — MCP format (?userId=)
    r = await client.get(f"/api/agent-context?userId={uid}")
    assert r.status_code == 200, r.text
    assert r.json()["user_id"] == uid

    # agent-context — missing param should 422
    r = await client.get("/api/agent-context")
    assert r.status_code == 422

    # cards/stats
    r = await client.get(f"/api/cards/stats?userId={uid}")
    assert r.status_code == 200, r.text
    stats = r.json()
    assert "due_today" in stats
    assert "streak" in stats
    assert "reviewed_today" in stats

    # study-sessions list (GET) — was returning 405 in prod
    r = await client.get(f"/api/study-sessions?user_id={uid}")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)

    # topics list
    r = await client.get(f"/api/topics?user_id={uid}")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


# ── Topic creation flow ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_topic_start_and_list(client, db):
    """Create topic via API, verify it appears in list."""
    user = await _make_user(db, "topics@flow.test")
    uid = user.id

    # Create topic via API — was returning 500 in prod
    r = await client.post("/api/topics/start", json={"user_id": uid, "name": "Kubernetes basics"})
    assert r.status_code == 201, r.text
    topic = r.json()
    assert topic["name"] == "Kubernetes basics"
    assert topic["status"] == "active"
    tid = topic["id"]

    # Should appear in list
    r = await client.get(f"/api/topics?user_id={uid}")
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert tid in ids

    # GET single topic
    r = await client.get(f"/api/topics/{tid}")
    assert r.status_code == 200
    assert r.json()["id"] == tid


# ── Capsule generation flow ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_capsule_generation_flow(client, db):
    """Full capsule generation: add material → generate → wait → capsule ready."""
    user = await _make_user(db, "capsule@flow.test")
    uid = user.id
    topic = await _make_topic(db, uid, "Python asyncio")
    tid = topic.id

    await _add_text_material(
        db, tid, uid,
        content="asyncio — библиотека для асинхронного программирования в Python. "
                "Coroutines, event loop, Tasks, gather — ключевые концепты.",
        name="Intro to asyncio",
    )

    # Generate capsule
    r = await client.post(f"/api/topics/{tid}/capsule/generate", json={"user_id": uid})
    assert r.status_code == 201, r.text
    cid = r.json()["capsule_id"]
    assert cid

    # Wait for background task (fallback in test env, near-instant)
    capsule = await _poll_capsule(client, cid, timeout=5.0)
    assert capsule, f"Capsule never became ready, last state: {capsule}"
    assert capsule["status"] == "ready"
    assert len(capsule["content_md"]) > 10
    assert capsule["topic_id"] == tid


@pytest.mark.asyncio
async def test_capsule_generate_requires_materials(client, db):
    """Generating capsule without materials returns 422."""
    user = await _make_user(db, "nocaps@flow.test")
    uid = user.id
    topic = await _make_topic(db, uid, "Empty topic")
    tid = topic.id

    r = await client.post(f"/api/topics/{tid}/capsule/generate", json={"user_id": uid})
    assert r.status_code == 422, r.text


# ── Study session flow ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_study_session_full_flow(client, db):
    """Full study session: create → background generates conspect + tasks → session active."""
    user = await _make_user(db, "session@flow.test")
    uid = user.id
    topic = await _make_topic(db, uid, "Docker containers")
    tid = topic.id

    await _add_text_material(
        db, tid, uid,
        content="Docker — платформа для контейнеризации. Образы, контейнеры, Dockerfile.",
    )

    # Create session
    r = await client.post("/api/study-sessions", json={"user_id": uid, "topic_id": tid})
    assert r.status_code == 201, r.text
    body = r.json()
    sid = body["session"]["id"]
    assert body["generation_status"] == "generating"
    assert body["generation_error"] is None

    # Wait for background generation (fallback templates in test env)
    tasks = await _poll_tasks(client, uid, sid, timeout=4.0)
    assert len(tasks) == 2, f"Expected 2 tasks, got {len(tasks)}"
    task_types = {t["type"] for t in tasks}
    assert "theory" in task_types
    assert "mini_project" in task_types

    # Session should be active with conspect
    r = await client.get(f"/api/study-sessions/{sid}")
    assert r.status_code == 200
    session = r.json()
    assert session["status"] == "active"
    assert len(session["conspect_md"]) > 50

    # GET sessions list should include this session
    r = await client.get(f"/api/study-sessions?user_id={uid}")
    assert r.status_code == 200
    sids = [s["id"] for s in r.json()]
    assert sid in sids


# ── Cards flow ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cards_flow(client, db):
    """Create capsule → create cards from capsule → review cards → check streak."""
    from app.repositories import capsule_repo
    from app.models.capsule import Capsule
    from app.models.review_question import ReviewQuestion

    user = await _make_user(db, "cards@flow.test")
    uid = user.id
    topic = await _make_topic(db, uid, "SQL basics")
    tid = topic.id

    # Create a ready capsule directly in DB
    capsule = Capsule(
        user_id=uid, topic_id=tid,
        content_md="## SQL\n\nSELECT, INSERT, UPDATE, DELETE.",
        content_html="<h2>SQL</h2>",
        summary="SQL basics capsule",
        status="ready",
    )
    db.add(capsule)
    await db.commit()
    await db.refresh(capsule)
    cid = capsule.id

    # Add review questions
    for i, (q, a) in enumerate([
        ("Что делает SELECT?", "Выбирает данные"),
        ("Что делает INSERT?", "Вставляет данные"),
    ]):
        db.add(ReviewQuestion(capsule_id=cid, question=q, correct_answer=a, difficulty=i + 1))
    await db.commit()

    # Create cards from capsule
    r = await client.post("/api/cards/from-capsule", json={"user_id": uid, "capsule_id": cid})
    assert r.status_code in (200, 201), r.text

    # Check due cards
    r = await client.get(f"/api/cards/due?userId={uid}")
    assert r.status_code == 200
    due = r.json()
    assert len(due) >= 1
    assert "card_id" in due[0]  # field is card_id, not id

    # Log an attempt on first card
    card_id = due[0]["card_id"]
    r = await client.post(f"/api/cards/{card_id}/attempt", json={
        "user_id": uid, "rating": 4, "user_answer": "Выбирает данные из таблицы"
    })
    assert r.status_code in (200, 201), r.text

    # cards/stats — was returning 500 in prod
    r = await client.get(f"/api/cards/stats?userId={uid}")
    assert r.status_code == 200, r.text
    stats = r.json()
    assert stats["reviewed_today"] >= 1
