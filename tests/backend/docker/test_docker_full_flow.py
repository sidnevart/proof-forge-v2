"""
End-to-end integration test covering the full user flow against Docker stack.

Exercises real PostgreSQL, real background tasks, and the mock LLM pipeline:
  1. Create user (dev-token) → verify profile created
  2. Create topic → add materials
  3. Study session → AI conspect + tasks
  4. Capsule generation → AI content + review questions
  5. Cards from capsule → due cards → review → streak
"""
import asyncio
import os

import httpx
import pytest

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


@pytest.mark.asyncio
async def test_full_user_flow():
    """Complete user flow: topic → study → capsule → cards → review."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as client:
        # ── Step 1: Create user ────────────────────────────────────────────────
        r = await client.post("/api/auth/dev-token", json={
            "email": "docker-full@pf.io",
            "display_name": "FullFlow",
        })
        assert r.status_code == 200, f"dev-token failed: {r.text}"
        user_id = r.json()["user_id"]

        # Verify user was created and we can fetch the profile
        r = await client.get(f"/api/agent-context?user_id={user_id}")
        assert r.status_code == 200
        assert r.json()["user_id"] == user_id

        # ── Step 2: Create topic with materials ────────────────────────────────
        r = await client.post("/api/topics/start", json={
            "user_id": user_id, "name": "React hooks integration",
        })
        assert r.status_code == 201
        topic_id = r.json()["id"]

        # Add a material
        r = await client.post(
            f"/api/topics/{topic_id}/materials/file?user_id={user_id}",
            files={"file": ("hooks.md", b"useState and useEffect in React. Manage state.", "text/markdown")},
        )
        assert r.status_code == 201

        # Topic appears in list
        r = await client.get(f"/api/topics?user_id={user_id}")
        topic_ids = [t["id"] for t in r.json()]
        assert topic_id in topic_ids

        # ── Step 3: Start study session ────────────────────────────────────────
        r = await client.post("/api/study-sessions", json={
            "user_id": user_id, "topic_id": topic_id,
        })
        assert r.status_code == 201
        body = r.json()
        session_id = body["session"]["id"]
        assert body["session"]["status"] == "generating" or body["session"]["status"] == "active"

        # Wait for session to become active (background AI generation)
        for i in range(30):
            await asyncio.sleep(0.5)
            r = await client.get(f"/api/study-sessions/{session_id}")
            assert r.status_code == 200
            session = r.json()
            if session["status"] == "active":
                break
        assert session["status"] == "active", f"Session never became active: {session}"
        assert len(session["conspect_md"]) > 50, "No conspect generated"

        # ── Step 4: Generate capsule ───────────────────────────────────────────
        r = await client.post(f"/api/topics/{topic_id}/capsule/generate", json={
            "user_id": user_id,
        })
        assert r.status_code == 201
        capsule_id = r.json()["capsule_id"]

        # Wait for capsule to be ready
        capsule = None
        for i in range(30):
            await asyncio.sleep(0.5)
            r = await client.get(f"/api/capsules/{capsule_id}")
            if r.status_code == 200 and r.json()["status"] == "ready":
                capsule = r.json()
                break
        assert capsule is not None, "Capsule never became ready"
        assert len(capsule["review_questions"]) == 6, "Expected 6 review questions"
        assert len(capsule["content_md"]) > 100

        # ── Step 5: Create cards from capsule ──────────────────────────────────
        r = await client.post("/api/cards/from-capsule", json={
            "user_id": user_id, "capsule_id": capsule_id,
        })
        assert r.status_code in (200, 201), f"from-capsule failed: {r.text}"

        # ── Step 6: Review a due card ──────────────────────────────────────────
        due = []
        for i in range(10):
            r = await client.get(f"/api/cards/due?userId={user_id}&limit=10")
            if r.status_code == 200 and r.json():
                due = r.json()
                break
            await asyncio.sleep(0.5)
        assert len(due) >= 1, "No due cards found"

        # Pick the first capsule-sourced card for review (topic cards use a different endpoint)
        card = next((c for c in due if c["source"] == "capsule"), due[0])
        card_id = card["card_id"]

        if card["source"] == "topic":
            attempt_url = f"/api/cards/topic/{card_id}/attempt"
        else:
            attempt_url = f"/api/cards/{card_id}/attempt"

        r = await client.post(attempt_url, json={
            "user_id": user_id, "rating": 4,
            "user_answer": card["correct_answer"],
        })
        assert r.status_code in (200, 201), f"card attempt failed: {r.text}"

        # ── Step 7: Verify stats updated ───────────────────────────────────────
        r = await client.get(f"/api/cards/stats?userId={user_id}")
        assert r.status_code == 200
        stats = r.json()
        assert stats["reviewed_today"] >= 1
        print(f"Flow complete: reviewed={stats['reviewed_today']}, streak={stats['streak']}")


@pytest.mark.asyncio
async def test_health_endpoint():
    """Health endpoint returns 200."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10) as client:
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
