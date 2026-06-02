import pytest
from app.repositories import user_repo, topic_repo, capsule_repo, review_repo
from app.schemas.user import UserCreate
from app.schemas.topic import TopicStart
from app.schemas.capsule import CapsuleCreate, ReviewQuestionIn
from app.schemas.review import ReviewAnswerCreate


@pytest.mark.asyncio
async def test_store_review_answer(db):
    user = await user_repo.create_user(db, UserCreate(email="rev@example.com", display_name="Rev"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Closures"))
    capsule = await capsule_repo.store_capsule(db, CapsuleCreate(
        user_id=user.id,
        topic_id=topic.id,
        content_md="## Summary\nClosures capture scope.",
        summary="Closures capture scope.",
        review_questions=[ReviewQuestionIn(question="What is a closure?", correct_answer="A function + its lexical scope.", difficulty=1)],
    ))
    questions = await capsule_repo.get_capsule_questions(db, capsule.id)
    assert len(questions) == 1

    attempt = await review_repo.store_review_answer(db, ReviewAnswerCreate(
        user_id=user.id,
        question_id=questions[0].id,
        user_answer="A closure is a function that remembers its outer scope.",
        score=0.9,
        feedback="Correct. Well explained.",
        is_weak_spot=False,
    ))

    assert attempt.score == 0.9
    assert attempt.is_weak_spot is False


@pytest.mark.asyncio
async def test_weak_spot_created_on_low_score(db):
    user = await user_repo.create_user(db, UserCreate(email="weak@example.com", display_name="Weak"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Promises"))
    capsule = await capsule_repo.store_capsule(db, CapsuleCreate(
        user_id=user.id,
        topic_id=topic.id,
        content_md="## Summary\nPromises handle async.",
        summary="Promises handle async.",
        review_questions=[ReviewQuestionIn(question="What does Promise.all do?", correct_answer="Runs promises in parallel, resolves when all resolve.", difficulty=2)],
    ))
    questions = await capsule_repo.get_capsule_questions(db, capsule.id)

    await review_repo.store_review_answer(db, ReviewAnswerCreate(
        user_id=user.id,
        question_id=questions[0].id,
        user_answer="I don't know",
        score=0.1,
        feedback="Promise.all runs all promises in parallel.",
        is_weak_spot=True,
    ))

    weak_spots = await capsule_repo.get_user_weak_spots(db, user.id)
    assert len(weak_spots) >= 1
