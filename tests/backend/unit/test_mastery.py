import pytest


async def _identify(client, email="m@test.io"):
    r = await client.post("/api/users/identify", json={"email": email})
    return r.json()["id"]


async def _topic(client, user_id, name="T"):
    r = await client.post("/api/topics/start", json={"user_id": user_id, "name": name})
    return r.json()["id"]


@pytest.mark.asyncio
async def test_mastery_progression(client):
    """unknown → recognize → apply → explain via deterministic backend rules."""
    uid = await _identify(client, "mastery@test.io")
    tid = await _topic(client, uid)

    def rec(**kw):
        body = {"user_id": uid, "topic_id": tid, "concept": "closures", **kw}
        return client.post("/api/mastery/record", json=body)

    # theory → recognize
    r = await rec(kind="theory")
    assert r.json()["mastery_level"] == "recognize"

    # 1 practice diff2 q0.7 → still recognize (needs >=2 practice)
    r = await rec(kind="practice", difficulty=2, quality_score=0.7)
    assert r.json()["mastery_level"] == "recognize"

    # 2nd practice diff2 q0.8 → apply
    r = await rec(kind="practice", difficulty=2, quality_score=0.8)
    assert r.json()["mastery_level"] == "apply"

    # 3rd practice diff3 q0.95 struggle1 → explain
    r = await rec(kind="practice", difficulty=3, quality_score=0.95, struggle_passed=1)
    body = r.json()
    assert body["mastery_level"] == "explain"
    assert body["practice_reps"] == 3
    assert body["max_difficulty"] == 3


@pytest.mark.asyncio
async def test_mastery_progress_rollup(client):
    uid = await _identify(client, "rollup@test.io")
    tid = await _topic(client, uid)
    await client.post("/api/mastery/record", json={"user_id": uid, "topic_id": tid, "concept": "a", "kind": "theory"})

    r = await client.get(f"/api/mastery/progress?userId={uid}")
    data = r.json()
    assert data["rollup"]["total_concepts"] == 1
    assert data["concepts"][0]["badge"] == "🟨"


@pytest.mark.asyncio
async def test_mastery_invalid_kind(client):
    uid = await _identify(client, "bad@test.io")
    tid = await _topic(client, uid)
    r = await client.post("/api/mastery/record", json={"user_id": uid, "topic_id": tid, "concept": "x", "kind": "wrong"})
    assert r.status_code == 422
