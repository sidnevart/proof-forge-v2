import pytest
from app.repositories import user_repo, topic_repo, capsule_repo
from app.schemas.user import UserCreate
from app.schemas.topic import TopicStart
from app.schemas.capsule import CapsuleCreate, ReviewQuestionIn


SAMPLE_MD = """## Summary
JavaScript closures give inner functions access to outer scope variables.

## Concept Map
- Closure = function + lexical environment
- Captures variables by reference
- Used in event handlers, factories, memoization

## Weak Spots
- Difference between closure and class in terms of encapsulation

## Code Map
| File | Concepts |
|---|---|
| counter.js | factory pattern, state via closure |

## Review Tasks
See review_questions below.

## Replay
1. Read about lexical scope
2. Wrote counter.js using closures
3. Discovered partial application pattern

## Next Steps
- Study module pattern
- Practice with memoize()
- Compare to class-based encapsulation
"""


@pytest.mark.asyncio
async def test_store_capsule_renders_html(db):
    user = await user_repo.create_user(db, UserCreate(email="cap@example.com", display_name="Cap"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="JS Closures"))

    capsule = await capsule_repo.store_capsule(db, CapsuleCreate(
        user_id=user.id,
        topic_id=topic.id,
        content_md=SAMPLE_MD,
        summary="JavaScript closures give inner functions access to outer scope variables.",
        review_questions=[
            ReviewQuestionIn(question="What is a closure?", correct_answer="Function + lexical environment.", difficulty=1),
            ReviewQuestionIn(question="How do closures differ from classes?", correct_answer="Closures use lexical scope; classes use prototype chain.", difficulty=2),
        ],
    ))

    assert capsule.id is not None
    assert "<h2>Summary</h2>" in capsule.content_html
    assert capsule.summary.startswith("JavaScript closures")

    questions = await capsule_repo.get_capsule_questions(db, capsule.id)
    assert len(questions) == 2
    assert questions[0].difficulty == 1


@pytest.mark.asyncio
async def test_get_capsule_returns_with_questions(db):
    user = await user_repo.create_user(db, UserCreate(email="cap2@example.com", display_name="Cap2"))
    topic = await topic_repo.start_topic(db, TopicStart(user_id=user.id, name="Async/Await"))
    capsule = await capsule_repo.store_capsule(db, CapsuleCreate(
        user_id=user.id,
        topic_id=topic.id,
        content_md="## Summary\nAsync/await is syntactic sugar over Promises.",
        summary="Async/await is syntactic sugar over Promises.",
        review_questions=[ReviewQuestionIn(question="What does await do?", correct_answer="Pauses execution until Promise resolves.", difficulty=1)],
    ))

    fetched = await capsule_repo.get_capsule(db, capsule.id)
    assert fetched is not None
    assert fetched.topic_id == topic.id
