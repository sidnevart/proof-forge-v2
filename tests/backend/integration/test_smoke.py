import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_full_flow(client):
    # create user
    r = await client.post("/api/users", json={"email": "smoke@example.com", "display_name": "Smoke"})
    assert r.status_code == 201
    user_id = r.json()["id"]

    # get profile
    r = await client.get(f"/api/users/{user_id}/profile")
    assert r.status_code == 200
    assert r.json()["skill_level"] == "beginner"

    # start topic
    r = await client.post("/api/topics/start", json={"user_id": user_id, "name": "Closures"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    # log event
    r = await client.post("/api/events", json={
        "user_id": user_id,
        "event_type": "note_added",
        "payload": {"text": "Closures capture outer scope", "topic_id": topic_id},
    })
    assert r.status_code == 201

    # store capsule
    r = await client.post("/api/capsules", json={
        "user_id": user_id,
        "topic_id": topic_id,
        "content_md": "## Summary\nClosures capture scope.\n\n## Concept Map\n- closure = fn + scope",
        "summary": "Closures capture scope.",
        "review_questions": [
            {"question": "What is a closure?", "correct_answer": "fn + lexical scope", "difficulty": 1}
        ],
    })
    assert r.status_code == 201
    capsule_data = r.json()
    capsule_id = capsule_data["id"]
    assert "<h2>Summary</h2>" in capsule_data["content_html"]
    assert len(capsule_data["review_questions"]) == 1
    question_id = capsule_data["review_questions"][0]["id"]

    # get capsule
    r = await client.get(f"/api/capsules/{capsule_id}")
    assert r.status_code == 200

    # answer review
    r = await client.post("/api/reviews/answer", json={
        "user_id": user_id,
        "question_id": question_id,
        "user_answer": "A closure is a function that captures its outer scope.",
        "score": 0.9,
        "feedback": "Correct.",
        "is_weak_spot": False,
    })
    assert r.status_code == 201
    assert r.json()["score"] == 0.9

    # get agent context
    r = await client.get(f"/api/agent-context?userId={user_id}")
    assert r.status_code == 200
    ctx = r.json()
    assert ctx["user_id"] == user_id
    assert len(ctx["capsules"]) >= 1
    assert len(ctx["recent_events"]) >= 1
