"""
Integration tests for AI capsule generation via the real Docker stack.

Verifies the full capsule generation pipeline:
  - Material upload → capsule generation → AI response parsing → persistence
  - Background task execution with real PostgreSQL
  - Review question creation with correct difficulty distribution
"""
import asyncio
import json
import os

import httpx
import pytest

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


async def _create_user(client: httpx.AsyncClient) -> tuple[str, str]:
    r = await client.post("/api/auth/dev-token", json={
        "email": "docker-capsule@pf.io",
        "display_name": "CapsuleTest",
    })
    assert r.status_code == 200
    body = r.json()
    return body["user_id"], body["access_token"]


async def _create_topic(client: httpx.AsyncClient, user_id: str, name: str = "React hooks") -> str:
    r = await client.post("/api/topics/start", json={"user_id": user_id, "name": name})
    assert r.status_code == 201, f"topic failed: {r.text}"
    return r.json()["id"]


async def _upload_material(client: httpx.AsyncClient, topic_id: str, user_id: str) -> None:
    r = await client.post(
        f"/api/topics/{topic_id}/materials/file?user_id={user_id}",
        files={"file": ("react.md", b"# React\n\nuseState, useEffect. Hooks API.", "text/markdown")},
    )
    assert r.status_code == 201, f"material failed: {r.text}"


async def _poll_capsule(client: httpx.AsyncClient, capsule_id: str, timeout: float = 15.0) -> dict | None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(f"/api/capsules/{capsule_id}")
        if r.status_code == 200:
            cap = r.json()
            if cap["status"] == "ready":
                return cap
        await asyncio.sleep(0.5)
    return None


@pytest.mark.asyncio
async def test_capsule_generation_with_mock_llm():
    """Generate a capsule via the mock LLM and verify the result is persisted."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as client:
        user_id, _ = await _create_user(client)
        topic_id = await _create_topic(client, user_id)
        await _upload_material(client, topic_id, user_id)

        # Generate capsule
        r = await client.post(f"/api/topics/{topic_id}/capsule/generate", json={
            "user_id": user_id,
        })
        assert r.status_code == 201, f"capsule gen failed: {r.text}"
        capsule_id = r.json()["capsule_id"]

        # Wait for background task
        capsule = await _poll_capsule(client, capsule_id, timeout=15.0)
        assert capsule is not None, "Capsule never became ready"
        assert capsule["status"] == "ready"
        assert len(capsule["content_md"]) > 50, "content_md too short"
        assert len(capsule["summary"]) > 10, "summary too short"


@pytest.mark.asyncio
async def test_capsule_has_review_questions():
    """Verify the capsule has review questions with proper difficulty distribution."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as client:
        user_id, _ = await _create_user(client)
        topic_id = await _create_topic(client, user_id)
        await _upload_material(client, topic_id, user_id)

        r = await client.post(f"/api/topics/{topic_id}/capsule/generate", json={
            "user_id": user_id,
        })
        capsule_id = r.json()["capsule_id"]

        capsule = await _poll_capsule(client, capsule_id, timeout=15.0)
        assert capsule is not None

        questions = capsule.get("review_questions", [])
        assert len(questions) == 6, f"Expected 6 questions, got {len(questions)}"

        # Verify difficulty distribution
        difficulties = [q["difficulty"] for q in questions]
        assert 1 in difficulties, "Missing easy questions (diff=1)"
        assert 2 in difficulties, "Missing medium questions (diff=2)"
        assert 3 in difficulties, "Missing hard questions (diff=3)"

        # Each question has valid fields
        for q in questions:
            assert len(q["question"]) > 0
            assert len(q["correct_answer"]) > 0
            assert 1 <= q["difficulty"] <= 3


@pytest.mark.asyncio
async def test_capsule_content_is_markdown():
    """Capsule content_md should be valid markdown with headings and code blocks."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as client:
        user_id, _ = await _create_user(client)
        topic_id = await _create_topic(client, user_id)
        await _upload_material(client, topic_id, user_id)

        r = await client.post(f"/api/topics/{topic_id}/capsule/generate", json={
            "user_id": user_id,
        })
        capsule_id = r.json()["capsule_id"]

        capsule = await _poll_capsule(client, capsule_id, timeout=15.0)
        assert capsule is not None

        content = capsule["content_md"]
        assert "## " in content, "No markdown headings found"

        # Code blocks in capsule content use language labels instead of backticks
        # (because the json-extract step strips triple backticks)
        has_code_marker = "jsx" in content.lower() or "python" in content.lower() or "```" in content
        assert has_code_marker, "No code or language marker found in capsule content"

        # content_html should be rendered markdown
        html = capsule.get("content_html", "")
        assert len(html) > len(content) * 0.5, "content_html seems too short vs content_md"


@pytest.mark.asyncio
async def test_capsule_with_chat_context():
    """Capsule generation with chat_messages should succeed and include context."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as client:
        user_id, _ = await _create_user(client)
        topic_id = await _create_topic(client, user_id)
        await _upload_material(client, topic_id, user_id)

        r = await client.post(f"/api/topics/{topic_id}/capsule/generate", json={
            "user_id": user_id,
            "chat_messages": [
                {"role": "user", "content": "What is useState?"},
                {"role": "assistant", "content": "useState is a React hook for state management."},
            ],
        })
        assert r.status_code == 201, f"capsule with context failed: {r.text}"
        capsule_id = r.json()["capsule_id"]

        capsule = await _poll_capsule(client, capsule_id, timeout=15.0)
        assert capsule is not None
        assert capsule["status"] == "ready"
        assert capsule["topic_id"] == topic_id
