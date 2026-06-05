import pytest
from sqlalchemy import select

from app.models import Capsule, ReviewCard, ReviewQuestion, TopicCard
from app.repositories import review_card_repo
from app.repositories import topic_repo, user_repo
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate
from app.services import card_generation


@pytest.mark.asyncio
async def test_generate_cards_for_topic_persists_all_supported_card_types(db, monkeypatch):
    user = await user_repo.create_user(
        db,
        UserCreate(email="cards-gen@example.com", display_name="CardsGen"),
    )
    topic = await topic_repo.start_topic(
        db,
        TopicStart(user_id=user.id, name="Kotlin coroutines"),
    )

    async def fake_llm_cards(topic_name: str, context_md: str):
        assert topic_name == "Kotlin coroutines"
        assert "launch starts" in context_md
        return [
            {
                "type": "FLASHCARD",
                "front": "Что делает launch?",
                "back": "Запускает корутину без результата.",
                "difficulty": 1,
            },
            {
                "type": "FILL_BLANK",
                "front": "Метод ___ возвращает Deferred.",
                "back": "async",
                "difficulty": 1,
            },
            {
                "type": "CODE_REVIEW",
                "front": "```kotlin\nGlobalScope.launch { work() }\n```\nЧто здесь рискованно?",
                "back": "GlobalScope отвязывает работу от жизненного цикла.",
                "difficulty": 2,
            },
            {
                "type": "PRACTICAL",
                "front": "Как выбрать builder для параллельных сетевых запросов?",
                "back": "Использовать async для результатов и awaitAll для ожидания.",
                "difficulty": 3,
            },
        ]

    monkeypatch.setattr(card_generation, "_generate_cards_with_llm", fake_llm_cards)

    created = await card_generation.generate_cards_for_topic(
        topic.id,
        user.id,
        db,
        context_md="launch starts fire-and-forget work; async returns a Deferred",
    )

    assert [card.card_type for card in created] == [
        "FLASHCARD",
        "FILL_BLANK",
        "CODE_REVIEW",
        "PRACTICAL",
    ]
    assert [card.difficulty for card in created] == [1, 1, 2, 3]
    assert all(card.topic_id == topic.id for card in created)
    assert all(card.user_id == user.id for card in created)

    rows = await db.execute(select(TopicCard).where(TopicCard.topic_id == topic.id))
    assert len(rows.scalars().all()) == 4


@pytest.mark.asyncio
async def test_generate_cards_for_topic_skips_duplicate_fronts(db, monkeypatch):
    user = await user_repo.create_user(
        db,
        UserCreate(email="cards-dupes@example.com", display_name="CardsDupes"),
    )
    topic = await topic_repo.start_topic(
        db,
        TopicStart(user_id=user.id, name="SQL indexes"),
    )
    db.add(
        TopicCard(
            topic_id=topic.id,
            user_id=user.id,
            card_type="FLASHCARD",
            front="Что такое B-tree индекс?",
            back="Дерево поиска для ускорения чтения.",
            difficulty=1,
        )
    )
    await db.commit()

    async def fake_llm_cards(topic_name: str, context_md: str):
        return [
            {
                "type": "FLASHCARD",
                "front": "Что такое B-tree индекс?",
                "back": "Дублирующий ответ не должен сохраняться.",
                "difficulty": 1,
            },
            {
                "type": "PRACTICAL",
                "front": "Когда индекс замедляет запись?",
                "back": "Когда каждую вставку нужно отражать в структуре индекса.",
                "difficulty": 2,
            },
        ]

    monkeypatch.setattr(card_generation, "_generate_cards_with_llm", fake_llm_cards)

    created = await card_generation.generate_cards_for_topic(
        topic.id,
        user.id,
        db,
        context_md="indexes speed up reads but add write overhead",
    )

    assert len(created) == 1
    assert created[0].front == "Когда индекс замедляет запись?"

    rows = await db.execute(
        select(TopicCard).where(
            TopicCard.topic_id == topic.id,
            TopicCard.user_id == user.id,
        )
    )
    persisted = rows.scalars().all()
    assert len(persisted) == 2
    assert {card.front for card in persisted} == {
        "Что такое B-tree индекс?",
        "Когда индекс замедляет запись?",
    }


@pytest.mark.asyncio
async def test_due_cards_merge_capsule_and_topic_cards_and_topic_attempt_updates_sm2(db):
    user = await user_repo.create_user(
        db,
        UserCreate(email="cards-due@example.com", display_name="CardsDue"),
    )
    topic = await topic_repo.start_topic(
        db,
        TopicStart(user_id=user.id, name="PostgreSQL locks"),
    )
    capsule = Capsule(
        user_id=user.id,
        topic_id=topic.id,
        content_md="## Locks",
        content_html="<h2>Locks</h2>",
        summary="Locks",
        status="ready",
    )
    db.add(capsule)
    await db.commit()
    await db.refresh(capsule)

    question = ReviewQuestion(
        capsule_id=capsule.id,
        question="Что делает row lock?",
        correct_answer="Блокирует конкретную строку.",
        difficulty=1,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)

    review_card = ReviewCard(question_id=question.id, user_id=user.id)
    topic_card = TopicCard(
        topic_id=topic.id,
        user_id=user.id,
        card_type="PRACTICAL",
        front="Когда нужен SELECT FOR UPDATE?",
        back="Когда нужно прочитать строку и защитить её от конкурентного изменения.",
        difficulty=2,
    )
    db.add_all([review_card, topic_card])
    await db.commit()

    due = await review_card_repo.get_due_cards(db, user.id, limit=10)

    assert [(card["source"], card["card_type"]) for card in due] == [
        ("capsule", "FLASHCARD"),
        ("topic", "PRACTICAL"),
    ]
    assert due[0]["question"] == "Что делает row lock?"
    assert due[1]["question"] == "Когда нужен SELECT FOR UPDATE?"
    assert due[1]["correct_answer"] == "Когда нужно прочитать строку и защитить её от конкурентного изменения."

    updated = await review_card_repo.log_topic_card_attempt(
        db,
        topic_card.id,
        user.id,
        rating=4,
    )

    assert updated is not None
    assert updated.repetitions == 1
    assert updated.interval_days == 1
    assert updated.ease_factor > 2.5
