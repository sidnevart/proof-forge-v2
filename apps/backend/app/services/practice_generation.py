import json
import re
from typing import Any

import httpx

from app.models import Topic
from app.schemas.practice import PracticeTaskCreate, StudySessionCreate


# ── LLM helpers (mirrored from topics.py) ────────────────────────────────────

async def _llm_call(
    client: httpx.AsyncClient, settings: Any, prompt: str, max_tokens: int = 2000
) -> str:
    response = await client.post(
        f"{settings.llm_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.5,
        },
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start:end])


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _build_study_prompt(topic_name: str, materials: list[dict]) -> str:
    materials_block = ""
    for m in materials:
        preview = m["content_text"][:3000].replace("\n", " ")
        materials_block += f"\n\n--- Материал: {m['name']} ({m['type']}) ---\n{preview}"

    prompt = f"""Ты — эксперт-методист для IT-специалистов. На основе материалов по теме «{topic_name}» создай структурированную учебную сессию.

## Материалы
{materials_block}

---

Ответь ТОЛЬКО валидным JSON без markdown-блоков:

{{
  "conspect_md": "Структурированный markdown (500-800 слов). Разделы: ## Обзор, ## Ключевые концепции (с пояснениями), ## Практическое применение. Язык: русский (термины на языке оригинала).",
  "learning_goals": ["цель 1", "цель 2", "цель 3"],
  "theory_task": {{
    "title": "Краткое название теоретического задания",
    "instructions_md": "Инструкция для теоретического задания: что сделать, какие вопросы ответить, какой формат ответа. 150-300 слов."
  }},
  "mini_project_task": {{
    "title": "Краткое название практического задания",
    "instructions_md": "Инструкция для mini-project: что реализовать, какие файлы изменить, как проверить результат, что включить в рефлексию. 200-400 слов.",
    "expected_evidence": ["source_files", "diff", "test_output", "reflection"],
    "target_concepts": ["концепт 1", "концепт 2"]
  }}
}}

Если материалов мало — используй свои знания о теме."""
    return prompt


# ── AI generation ──────────────────────────────────────────────────────────────

async def generate_study_content(
    settings: Any, topic: Topic, materials: list[dict]
) -> tuple[StudySessionCreate, list[PracticeTaskCreate]] | None:
    """Call LLM to generate study session content."""
    if not settings.llm_api_key:
        raise RuntimeError("LLM не настроен")

    prompt = _build_study_prompt(topic.name, materials)

    async with httpx.AsyncClient(timeout=90) as client:
        raw = await _llm_call(client, settings, prompt, max_tokens=2500)
        parsed = _extract_json(raw)

    if "conspect_md" not in parsed:
        raise ValueError("LLM вернул ответ без conspect_md")

    session_create = StudySessionCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        conspect_md=parsed["conspect_md"],
        learning_goals=parsed.get("learning_goals", [f"Изучить {topic.name}"]),
    )

    theory_raw = parsed.get("theory_task", {})
    mini_raw = parsed.get("mini_project_task", {})

    theory = PracticeTaskCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        study_session_id="",  # filled by caller
        type="theory",
        title=theory_raw.get("title", f"Теория: {topic.name}"),
        instructions_md=theory_raw.get(
            "instructions_md",
            f"## Теоретический блок: {topic.name}\n\nРазбери ключевые концепции из конспекта.",
        ),
        target_concepts=mini_raw.get("target_concepts", [topic.name])[:1],
        difficulty=1,
        expected_evidence=["written_explanation"],
        check_commands=[],
    )

    mini = PracticeTaskCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        study_session_id="",  # filled by caller
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

    return session_create, [theory, mini]


# ── Fallback builders ──────────────────────────────────────────────────────────

def build_study_session(topic: Topic) -> StudySessionCreate:
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


def build_theory_task(session_id: str, topic: Topic) -> PracticeTaskCreate:
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


def build_mini_project_task(session_id: str, topic: Topic) -> PracticeTaskCreate:
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


def build_study_tasks(session_id: str, topic: Topic) -> list[PracticeTaskCreate]:
    """Build the ordered set of practice tasks for a study session.

    Matches study-mentor-v2 flow: theory first, then capstone mini-project.
    """
    return [
        build_theory_task(session_id, topic),
        build_mini_project_task(session_id, topic),
    ]
