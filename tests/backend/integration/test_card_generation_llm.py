"""
AI-integration tests for card generation.

These exercise the REAL ``_generate_cards_with_llm`` code path — JSON extraction,
card-type normalization, difficulty clamping, duplicate filtering and persistence —
by stubbing only the httpx transport layer with a fake OpenAI-compatible response.
This catches regressions in prompt-response parsing that whole-function mocks miss.
"""
import json

import httpx
import pytest

from app.config import settings
from app.models import TopicCard
from app.repositories import topic_repo, user_repo
from app.schemas.topic import TopicStart
from app.schemas.user import UserCreate
from app.services import card_generation
from sqlalchemy import select


def _chat_completion(content: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


class _FakeLLMClient:
    """Drop-in replacement for httpx.AsyncClient that returns a canned LLM response."""

    def __init__(self, content: str):
        self._content = content

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, headers=None, json=None):
        request = httpx.Request("POST", url)
        return httpx.Response(
            200, json=_chat_completion(self._content), request=request
        )


@pytest.fixture
def llm_enabled(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(card_generation.settings, "llm_api_key", "test-key")


@pytest.mark.asyncio
async def test_generate_cards_parses_llm_json_array(db, monkeypatch, llm_enabled):
    cards_json = json.dumps([
        {"type": "FLASHCARD", "front": "Что такое event loop?",
         "back": "Цикл, обрабатывающий очередь задач.", "difficulty": 1},
        {"type": "fill-blank", "front": "Метод ___ планирует микротаску.",
         "back": "queueMicrotask", "difficulty": 2},
        {"type": "CODE_REVIEW",
         "front": "```js\nsetTimeout(f, 0)\n```\nКогда выполнится f?",
         "back": "После текущего стека и микротасок.", "difficulty": 3},
        {"type": "PRACTICAL", "front": "Как избежать блокировки event loop?",
         "back": "Разбивать тяжёлые задачи и выносить в воркеры.", "difficulty": 2},
    ])
    # Wrap in markdown fences + preamble to mimic a reasoning model
    raw = f"Вот карточки:\n```json\n{cards_json}\n```"

    monkeypatch.setattr(card_generation.httpx, "AsyncClient", _FakeLLMClient(raw))

    user = await user_repo.create_user(
        db, UserCreate(email="llm-cards@example.com", display_name="LLMCards")
    )
    topic = await topic_repo.start_topic(
        db, TopicStart(user_id=user.id, name="JS event loop")
    )

    created = await card_generation.generate_cards_for_topic(
        topic.id, user.id, db, context_md="event loop schedules tasks and microtasks"
    )

    assert [c.card_type for c in created] == [
        "FLASHCARD", "FILL_BLANK", "CODE_REVIEW", "PRACTICAL"
    ]
    assert [c.difficulty for c in created] == [1, 2, 3, 2]

    rows = await db.execute(select(TopicCard).where(TopicCard.topic_id == topic.id))
    assert len(rows.scalars().all()) == 4


@pytest.mark.asyncio
async def test_generate_cards_clamps_difficulty_and_normalizes_unknown_type(
    db, monkeypatch, llm_enabled
):
    raw = json.dumps([
        {"type": "MYSTERY", "front": "Странный тип?", "back": "Должен стать FLASHCARD.",
         "difficulty": 9},
        {"type": "FLASHCARD", "front": "Нулевая сложность?", "back": "Должна стать 1.",
         "difficulty": 0},
    ])
    monkeypatch.setattr(card_generation.httpx, "AsyncClient", _FakeLLMClient(raw))

    user = await user_repo.create_user(
        db, UserCreate(email="llm-clamp@example.com", display_name="Clamp")
    )
    topic = await topic_repo.start_topic(
        db, TopicStart(user_id=user.id, name="Edge cases")
    )

    created = await card_generation.generate_cards_for_topic(
        topic.id, user.id, db, context_md="edge case handling"
    )

    assert created[0].card_type == "FLASHCARD"  # MYSTERY → FLASHCARD
    assert created[0].difficulty == 3           # 9 clamped to 3
    assert created[1].difficulty == 1           # 0 clamped to 1


@pytest.mark.asyncio
async def test_generate_cards_falls_back_when_no_api_key(db, monkeypatch):
    monkeypatch.setattr(card_generation.settings, "llm_api_key", "")

    user = await user_repo.create_user(
        db, UserCreate(email="llm-fallback@example.com", display_name="Fallback")
    )
    topic = await topic_repo.start_topic(
        db, TopicStart(user_id=user.id, name="Offline topic")
    )

    created = await card_generation.generate_cards_for_topic(
        topic.id, user.id, db, context_md="some context"
    )

    # Fallback path still produces usable cards without any LLM call
    assert len(created) >= 1
    assert all(c.front and c.back for c in created)


@pytest.mark.asyncio
async def test_generate_cards_raises_on_malformed_json(db, monkeypatch, llm_enabled):
    monkeypatch.setattr(
        card_generation.httpx, "AsyncClient", _FakeLLMClient("not json at all")
    )

    user = await user_repo.create_user(
        db, UserCreate(email="llm-bad@example.com", display_name="BadJSON")
    )
    topic = await topic_repo.start_topic(
        db, TopicStart(user_id=user.id, name="Broken")
    )

    with pytest.raises(ValueError):
        await card_generation.generate_cards_for_topic(
            topic.id, user.id, db, context_md="ctx"
        )


@pytest.mark.asyncio
async def test_background_wrapper_swallows_generation_errors(monkeypatch, llm_enabled):
    """The fire-and-forget wrapper must never raise into the request flow."""
    async def _boom(*args, **kwargs):
        raise RuntimeError("LLM exploded")

    monkeypatch.setattr(card_generation, "generate_cards_for_topic", _boom)

    # Should complete without propagating the RuntimeError.
    await card_generation.generate_cards_for_topic_background(
        "missing-topic", "missing-user", context_md="ctx"
    )
