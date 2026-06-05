import asyncio
import pytest

from app.repositories import topic_repo, user_repo
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate


async def _wait_for_tasks(client, user_id: str, session_id: str, timeout: float = 3.0) -> list:
    """Poll until background generation creates tasks for the given session (asc order)."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.1)
        res = await client.get(f"/api/practice-tasks?user_id={user_id}&status=active")
        tasks = [t for t in res.json() if t["study_session_id"] == session_id]
        if tasks:
            return sorted(tasks, key=lambda t: t["created_at"])
    return []


@pytest.mark.asyncio
async def test_create_study_session_generates_conspect_and_task(client, db):
    user = await user_repo.create_user(db, UserCreate(email="study@example.com", display_name="Study"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Go interfaces"))

    res = await client.post(
        "/api/study-sessions",
        json={"user_id": user.id, "topic_id": topic.id},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["session"]["topic_id"] == topic.id
    assert body["generation_status"] == "generating"
    assert body["generation_error"] is None

    session_id = body["session"]["id"]

    # Wait for background task (fails with no LLM key → fallback content created)
    tasks = await _wait_for_tasks(client, user.id, session_id)
    assert len(tasks) == 2
    assert tasks[0]["type"] == "theory"
    assert tasks[1]["type"] == "mini_project"

    session_res = await client.get(f"/api/study-sessions/{session_id}")
    assert "Go interfaces" in session_res.json()["conspect_md"]


@pytest.mark.asyncio
async def test_plugin_can_pair_list_tasks_and_submit(client, db):
    user = await user_repo.create_user(db, UserCreate(email="plugin@example.com", display_name="Plugin"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Python async"))

    created = await client.post("/api/study-sessions", json={"user_id": user.id, "topic_id": topic.id})
    session_id = created.json()["session"]["id"]

    # Wait for background generation to create tasks
    tasks = await _wait_for_tasks(client, user.id, session_id)
    # Select the mini_project task (second task after theory)
    task_id = tasks[1]["id"]

    paired = await client.post(
        "/api/ide-sessions/pair",
        json={"user_id": user.id, "ide_product": "IntelliJ IDEA", "plugin_version": "0.1.0"},
    )
    assert paired.status_code == 201

    listed = await client.get(f"/api/practice-tasks?user_id={user.id}&status=active")
    assert listed.status_code == 200
    listed_ids = [t["id"] for t in listed.json()]
    assert task_id in listed_ids

    submission = await client.post(
        f"/api/practice-tasks/{task_id}/submissions",
        json={
            "user_id": user.id,
            "ide_session_id": paired.json()["id"],
            "files": [{"path": "main.py", "content": "print('ok')"}],
            "diff": "diff --git a/main.py b/main.py",
            "test_output": "1 passed",
            "check_command": "pytest",
            "exit_code": 0,
            "reflection": "I handled the async flow.",
            "language": "python",
        },
    )
    assert submission.status_code == 201

    evaluated = await client.post(f"/api/submissions/{submission.json()['id']}/evaluate")
    assert evaluated.status_code == 201
    assert evaluated.json()["status"] == "passed"


@pytest.mark.asyncio
async def test_passing_submission_updates_mastery(client, db):
    user = await user_repo.create_user(db, UserCreate(email="mastery-bridge@example.com", display_name="Mastery"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="TypeScript narrowing"))

    created = await client.post("/api/study-sessions", json={"user_id": user.id, "topic_id": topic.id})
    session_id = created.json()["session"]["id"]
    tasks = await _wait_for_tasks(client, user.id, session_id)
    task_id = tasks[1]["id"]

    submission = await client.post(
        f"/api/practice-tasks/{task_id}/submissions",
        json={
            "practice_task_id": task_id,
            "user_id": user.id,
            "files": [{"path": "src/narrow.ts", "content": "export const ok = true"}],
            "test_output": "1 passed",
            "exit_code": 0,
            "reflection": "I used type guards to narrow union types.",
            "language": "typescript",
        },
    )

    evaluated = await client.post(f"/api/submissions/{submission.json()['id']}/evaluate")

    # Mastery should not update until follow-ups are answered
    progress_before = await client.get(f"/api/mastery/progress?userId={user.id}&topic={topic.id}")
    assert progress_before.status_code == 200

    # Answer follow-ups created by evaluation
    follow_ups = await client.get(f"/api/evaluations/{evaluated.json()['id']}/follow-ups")
    assert follow_ups.status_code == 200
    for fu in follow_ups.json():
        await client.post(
            f"/api/follow-ups/{fu['id']}/answer",
            json={"user_answer": "Good explanation", "score": 0.9, "feedback_md": "Passed"},
        )

    progress = await client.get(f"/api/mastery/progress?userId={user.id}&topic={topic.id}")
    assert progress.status_code == 200
    concepts = progress.json()["concepts"]
    assert concepts[0]["concept"] == "TypeScript narrowing"
    assert concepts[0]["practice_reps"] == 1


@pytest.mark.asyncio
async def test_complete_study_session_forges_capsule(client, db):
    user = await user_repo.create_user(db, UserCreate(email="complete-session@example.com", display_name="Complete"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Java streams"))

    created = await client.post("/api/study-sessions", json={"user_id": user.id, "topic_id": topic.id})
    session_id = created.json()["session"]["id"]

    # Wait for background generation to complete (fallback content in test env)
    await _wait_for_tasks(client, user.id, session_id)

    completed = await client.post(f"/api/study-sessions/{session_id}/complete", json={"user_id": user.id})

    assert completed.status_code == 201
    body = completed.json()
    assert body["session"]["status"] == "completed"
    assert body["capsule"]["topic_id"] == topic.id
    assert "Java streams" in body["capsule"]["content_md"]
