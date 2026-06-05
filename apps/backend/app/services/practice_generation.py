import asyncio
import json
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import httpx

from app.schemas.practice import PracticeTaskCreate, StudySessionCreate


@dataclass
class TopicInfo:
    id: str
    name: str
    user_id: str


# ── LLM helpers ───────────────────────────────────────────────────────────────

async def _llm_call(
    client: httpx.AsyncClient,
    settings: Any,
    prompt: str,
    max_tokens: int = 2000,
    temperature: float = 0.5,
    system: str | None = None,
) -> str:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    from app.services.llm_utils import http_post_with_retry
    response = await http_post_with_retry(
        client,
        f"{settings.llm_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://proof-forge.ru",
            "X-Title": "Grasp",
        },
        json_body={
            "model": settings.llm_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    )
    data = response.json()
    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning") or ""


async def _llm_stream_tokens(
    client: httpx.AsyncClient, settings: Any, prompt: str, max_tokens: int = 1500
) -> AsyncGenerator[str, None]:
    """Stream tokens from the LLM using SSE (OpenAI-compatible)."""
    from app.services.llm_utils import http_stream_with_retry
    async for token in http_stream_with_retry(
        client,
        f"{settings.llm_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://proof-forge.ru",
            "X-Title": "Grasp",
        },
        json_body={
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "max_tokens": max_tokens,
            "temperature": 0.5,
        },
    ):
        yield token


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start:end])


# ── Prompts ───────────────────────────────────────────────────────────────────

def _build_conspect_prompt(topic_name: str, materials: list[dict]) -> str:
    materials_block = ""
    for m in materials:
        preview = m["content_text"][:3000].replace("\n", " ")
        materials_block += f"\n\n--- Материал: {m['name']} ({m['type']}) ---\n{preview}"

    return f"""Ты — эксперт-методист для IT-специалистов. На основе материалов по теме «{topic_name}» напиши структурированный конспект.

## Материалы
{materials_block if materials_block else "(материалов нет — используй свои знания о теме)"}

---

Напиши конспект в формате Markdown (600-900 слов).
Структура: ## Обзор, ## Ключевые концепции (с пояснениями и примерами кода/псевдокода где уместно), ## Практическое применение, ## Типичные ошибки
Язык: русский (термины на языке оригинала).

Начинай сразу с конспекта, без предисловий:"""


def _build_tasks_prompt(topic_name: str, conspect_md: str) -> str:
    return f"""На основе конспекта по теме «{topic_name}» создай учебные задания.

## Конспект
{conspect_md[:2000]}

---

ВАЖНО: ответь ТОЛЬКО валидным JSON. Никаких размышлений, никаких объяснений, только JSON.

{{
  "learning_goals": ["цель 1", "цель 2", "цель 3"],
  "theory_task": {{
    "title": "Краткое название теоретического задания",
    "instructions_md": "Инструкция для теоретического задания (150-300 слов)"
  }},
  "mini_project_task": {{
    "title": "Краткое название практического задания",
    "instructions_md": "Инструкция для mini-project (200-400 слов)",
    "expected_evidence": ["source_files", "diff", "test_output", "reflection"],
    "target_concepts": ["концепт 1", "концепт 2"]
  }}
}}"""


# ── Streaming generation ───────────────────────────────────────────────────────

async def stream_conspect_to_queue(
    settings: Any,
    topic: TopicInfo,
    materials: list[dict],
    q: asyncio.Queue,
) -> str:
    """Stream conspect tokens to SSE queue. Returns conspect_md."""
    await q.put(("phase_change", {"phase": "conspect", "label": "Пишу конспект..."}))

    conspect_md = ""
    prompt_conspect = _build_conspect_prompt(topic.name, materials)

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        async for token in _llm_stream_tokens(client, settings, prompt_conspect, max_tokens=1500):
            conspect_md += token
            await q.put(("token", {"content": token}))

    if not conspect_md.strip():
        raise ValueError("LLM вернул пустой конспект")

    return conspect_md


async def generate_tasks_from_conspect(
    settings: Any,
    topic: TopicInfo,
    conspect_md: str,
    q: asyncio.Queue,
) -> tuple[list[str], list[PracticeTaskCreate]]:
    """Generate tasks from conspect. Returns (learning_goals, task_creates)."""
    await q.put(("phase_change", {"phase": "tasks", "label": "Создаю задания..."}))

    prompt_tasks = _build_tasks_prompt(topic.name, conspect_md)

    async with httpx.AsyncClient(timeout=120.0) as client:
        raw = await _llm_call(
            client,
            settings,
            prompt_tasks,
            max_tokens=3000,
            temperature=0.1,
            system="You are a JSON-only API. Output ONLY the JSON object, no preamble, no markdown fences, no explanations.",
        )
        parsed = _extract_json(raw)

    theory_raw = parsed.get("theory_task", {})
    mini_raw = parsed.get("mini_project_task", {})

    theory = PracticeTaskCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        study_session_id="",
        type="theory",
        title=theory_raw.get("title", f"Теория: {topic.name}"),
        instructions_md=theory_raw.get(
            "instructions_md",
            f"## Теоретический блок: {topic.name}\n\nРазбери ключевые концепции из конспекта.",
        ),
        target_concepts=[topic.name],
        difficulty=1,
        expected_evidence=["written_explanation"],
        check_commands=[],
    )

    mini = PracticeTaskCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        study_session_id="",
        type="mini_project",
        title=mini_raw.get("title", f"Mini-project: {topic.name}"),
        instructions_md=mini_raw.get(
            "instructions_md",
            f"## Задание\n\nРеализуй проект по теме {topic.name}.",
        ),
        target_concepts=mini_raw.get("target_concepts", [topic.name]),
        difficulty=2,
        expected_evidence=mini_raw.get(
            "expected_evidence", ["source_files", "diff", "test_output", "reflection"]
        ),
        check_commands=[],
    )

    learning_goals = parsed.get("learning_goals", [f"Изучить {topic.name}"])
    return learning_goals, [theory, mini]


async def stream_study_content_to_queue(
    settings: Any,
    topic: TopicInfo,
    materials: list[dict],
    q: asyncio.Queue,
) -> tuple[str, list[str], list[PracticeTaskCreate]]:
    """Stream conspect tokens to SSE queue, then generate tasks.
    Returns (conspect_md, learning_goals, task_creates).
    """
    if not settings.llm_api_key:
        raise RuntimeError("LLM не настроен")

    conspect_md = await stream_conspect_to_queue(settings, topic, materials, q)
    learning_goals, task_creates = await generate_tasks_from_conspect(
        settings, topic, conspect_md, q
    )
    return conspect_md, learning_goals, task_creates


# ── Fallback builders ──────────────────────────────────────────────────────────

def build_study_session(topic: TopicInfo) -> StudySessionCreate:
    return StudySessionCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        conspect_md=(
            f"## Конспект: {topic.name}\n\n"
            "Сессия сфокусирована на понимании ключевых концепций через короткую теорию "
            "и практику в реальной IDE.\n\n"
            "## План\n\n"
            "1. **Теория** — разберём ключевые концепции.\n"
            "2. **Mini-project** — реализуй решение локально и отправь evidence через JetBrains plugin.\n"
        ),
        learning_goals=[
            f"Understand {topic.name} at conceptual level",
            f"Apply {topic.name} in a small real project",
        ],
    )


def build_theory_task(session_id: str, topic: TopicInfo) -> PracticeTaskCreate:
    return PracticeTaskCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        study_session_id=session_id,
        type="theory",
        title=f"Теория: {topic.name}",
        instructions_md=(
            f"## Теоретический блок: {topic.name}\n\n"
            "Прочитай конспект сессии и подготовь краткое объяснение:\n\n"
            "- Что делает эта концепция?\n"
            "- Зачем она нужна?\n"
            "- В каких ситуациях применяется?\n\n"
            "Это подготовка к mini-project."
        ),
        target_concepts=[topic.name],
        difficulty=1,
        expected_evidence=["written_explanation"],
        check_commands=[],
    )


def build_mini_project_task(session_id: str, topic: TopicInfo) -> PracticeTaskCreate:
    return PracticeTaskCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        study_session_id=session_id,
        type="mini_project",
        title=f"Mini-project: {topic.name}",
        instructions_md=(
            f"## Задание\n\n"
            f"Создай небольшой проект или измени текущий проект так, чтобы показать понимание темы "
            f"**{topic.name}**.\n\n"
            "## Что отправить\n\n"
            "- измененные исходные файлы или diff;\n"
            "- вывод тестов или команды проверки, если есть;\n"
            "- короткую рефлексию: что сделал, где были сложности, какие trade-offs выбрал.\n"
        ),
        target_concepts=[topic.name],
        difficulty=2,
        expected_evidence=["source_files", "diff", "test_output", "reflection"],
        check_commands=[],
    )


def build_study_tasks(session_id: str, topic: TopicInfo) -> list[PracticeTaskCreate]:
    return [
        build_theory_task(session_id, topic),
        build_mini_project_task(session_id, topic),
    ]
