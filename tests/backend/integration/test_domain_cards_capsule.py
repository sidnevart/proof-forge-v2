"""Integration tests for the topic-filtered due-cards endpoint and capsule rename."""
import pytest

from app.models import Capsule, ReviewQuestion, ReviewCard, TopicCard
from app.repositories import topic_repo, user_repo
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_due_cards_filter_by_topic(client, db):
    user = await user_repo.create_user(db, UserCreate(email="cardfilter@example.com", display_name="C"))
    topic_a = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Topic A"))
    topic_b = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Topic B"))

    # One topic card per topic, both due now.
    db.add(TopicCard(topic_id=topic_a.id, user_id=user.id, front="A-front", back="A-back"))
    db.add(TopicCard(topic_id=topic_b.id, user_id=user.id, front="B-front", back="B-back"))
    await db.commit()

    # No filter → both topics' cards.
    res_all = await client.get(f"/api/cards/due?userId={user.id}&limit=50")
    assert res_all.status_code == 200
    topic_ids_all = {c["topic_id"] for c in res_all.json()}
    assert {topic_a.id, topic_b.id} <= topic_ids_all

    # Filter by topic A → only A's card.
    res_a = await client.get(f"/api/cards/due?userId={user.id}&limit=50&topicId={topic_a.id}")
    assert res_a.status_code == 200
    rows = res_a.json()
    assert len(rows) == 1
    assert rows[0]["topic_id"] == topic_a.id
    assert rows[0]["question"] == "A-front"


@pytest.mark.asyncio
async def test_card_stats_filter_by_topic(client, db):
    user = await user_repo.create_user(db, UserCreate(email="cardstats@example.com", display_name="S"))
    topic_a = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Stat A"))
    topic_b = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Stat B"))
    db.add(TopicCard(topic_id=topic_a.id, user_id=user.id, front="qa", back="aa"))
    db.add(TopicCard(topic_id=topic_b.id, user_id=user.id, front="qb", back="ab"))
    await db.commit()

    stats_all = (await client.get(f"/api/cards/stats?userId={user.id}")).json()
    assert stats_all["due_today"] >= 2  # counts TopicCards now, not just ReviewCards

    stats_a = (await client.get(f"/api/cards/stats?userId={user.id}&topicId={topic_a.id}")).json()
    assert stats_a["due_today"] == 1


@pytest.mark.asyncio
async def test_capsule_rename(client, db):
    user = await user_repo.create_user(db, UserCreate(email="rename@example.com", display_name="R"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Rename topic"))
    capsule = Capsule(
        user_id=user.id,
        topic_id=topic.id,
        content_md="# body",
        content_html="<h1>body</h1>",
        summary="Auto summary",
        status="ready",
    )
    db.add(capsule)
    await db.commit()
    await db.refresh(capsule)

    # Before rename, title is null → frontend falls back to summary.
    got = (await client.get(f"/api/capsules/{capsule.id}")).json()
    assert got["title"] is None
    assert got["summary"] == "Auto summary"

    # Rename.
    patched = await client.patch(f"/api/capsules/{capsule.id}", json={"title": "My title"})
    assert patched.status_code == 200
    assert patched.json()["title"] == "My title"
    assert patched.json()["summary"] == "Auto summary"  # summary preserved

    # Persisted.
    reread = (await client.get(f"/api/capsules/{capsule.id}")).json()
    assert reread["title"] == "My title"


@pytest.mark.asyncio
async def test_capsule_rename_404(client, db):
    res = await client.patch("/api/capsules/does-not-exist", json={"title": "x"})
    assert res.status_code == 404
