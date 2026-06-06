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
        fallback_model=getattr(settings, "llm_fallback_model", None),
    )
    data = response.json()
    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning") or ""


async def _llm_stream_tokens(
    client: httpx.AsyncClient,
    settings: Any,
    prompt: str,
    max_tokens: int = 4000,
    system: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream tokens from the LLM using SSE (OpenAI-compatible)."""
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

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
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens,
            "temperature": 0.5,
        },
        fallback_model=getattr(settings, "llm_fallback_model", None),
    ):
        yield token


def _extract_json(text: str) -> dict:
    # Strip markdown code fences and backticks
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    # Find the outermost JSON object (handles reasoning-model preamble)
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in LLM response (len={len(text)})")
    # Find matching closing brace
    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        raise ValueError("Unmatched braces in LLM response")
    return json.loads(text[start:end])


# ── Prompts ───────────────────────────────────────────────────────────────────

CONSPECT_SYSTEM_PROMPT = (
    "Ты — сильный учебный ментор для IT-специалистов. Объясняешь глубоко, но «на пальцах»: "
    "каждую идею сопровождаешь бытовой аналогией, наглядным примером и, где уместно, схемой. "
    "Принцип подачи: наблюдение → гипотеза → эксперимент → решение.\n\n"
    "Форматирование (строго соблюдай — это влияет на читаемость):\n"
    "- Используй чёткую иерархию заголовков: ## для секций, ### для подсекций. "
    "НИКОГДА не ставь два заголовка подряд без текста между ними.\n"
    "- Каждый параграф — 2-4 предложения. Разделяй параграфы пустой строкой. "
    "Никаких «стен текста» по 8-10 предложений подряд.\n"
    "- Основные секции разделяй горизонтальной чертой `---` (с пустой строкой до и после).\n"
    "- Внутри секции «Ключевые концепции» каждая концепция начинается с `### Название`, "
    "затем 1-2 абзаца объяснения, затем аналогия или код — и пустая строка перед следующей.\n"
    "- Для списков используй маркированные списки (звёздочки), не плотный текст.\n"
    "- **Жирным** выделяй ключевые термины при первом упоминании.\n"
    "- Для любого процесса или архитектуры — диаграмма Mermaid в fenced-блоке ```mermaid "
    "(синтаксис flowchart TD / sequenceDiagram). Минимум 1-2 диаграммы на конспект.\n"
    "- Для сравнений (подходы, trade-offs) — Markdown-таблица.\n"
    "- Код — в fenced-блоках с языком (```python, ```ts и т.п.).\n"
    "- Не оставляй HTML-теги кроме обычного Markdown.\n"
    "Язык: русский, технические термины — на языке оригинала."
)


def _build_conspect_prompt(topic_name: str, materials_block: str) -> str:
    if not materials_block.strip():
        materials_block = "(материалов нет — используй свои знания о теме)"

    return f"""На основе материалов по теме «{topic_name}» напиши подробный, наглядный конспект.

## Материалы
{materials_block}

---

Напиши развёрнутый конспект в формате Markdown (1500-2200 слов). Объясняй подробно и
«на пальцах», не экономь на примерах и схемах.

**Правила оформления (влияют на читаемость — соблюдай строго):**
- Каждый параграф — 2-4 предложения. Разделяй параграфы пустой строкой.
- Секции ## разделяй горизонтальной чертой `---`.
- Внутри «Ключевых концепций» каждая концепция — ### заголовок + 1-2 абзаца + код/аналогия.
  Между концепциями — пустая строка.
- Код и mermaid-диаграммы — на отдельных строках, с пустой строкой до и после.

**Структура конспекта:**

## Обзор
[3-4 предложения: что это, зачем нужно и какую проблему решает. Один абзац.]

**Аналогия на пальцах:** [бытовой образ в 1-2 предложениях. Отдельный абзац.]

```mermaid
flowchart TD
  [Схема общей картины темы]
```

---

## Ключевые концепции

### [Название концепции 1]
[1-2 абзаца: объяснение простыми словами. Максимум 4 предложения в абзаце.]

**Аналогия на пальцах:** [коротко]

[Пример кода если уместно — fenced block с языком]

### [Название концепции 2]
[аналогично — заголовок, объяснение, аналогия, код]

[3-5 концепций, каждая с ### заголовком. Не сливай их в один текст.]

---

## Как это работает шаг за шагом
[Пошаговый разбор на конкретном примере. Каждый шаг — либо **жирный** подзаголовок с 1-2 предложениями, либо элемент нумерованного списка. Если есть последовательность взаимодействий — ```mermaid sequenceDiagram.]

---

## Сравнение подходов
[Markdown-таблица: вариант / когда использовать / плюсы / минусы.]

---

## Практическое применение
[2-3 абзаца: реальные сценарии, типичные паттерны. Можно маркированным списком.]

---

## Типичные ошибки

### Ошибка 1: [название]
❌ Неправильно:
```[lang]
[код с ошибкой]
```
✅ Правильно:
```[lang]
[исправленный код]
```
[1-2 предложения: почему так и как избежать.]

### Ошибка 2: [аналогично]
[2-3 ошибки, каждая с ### заголовком, кодом и объяснением.]

---

## Важно запомнить
- [Ключевой тезис 1 — одно предложение]
- [Ключевой тезис 2]
- [4-6 тезисов маркированным списком]

Начинай сразу с конспекта, без предисловий."""


def _build_tasks_prompt(topic_name: str, conspect_md: str) -> str:
    return f"""На основе конспекта по теме «{topic_name}» создай учебные задания в трёх уровнях.

## Конспект
{conspect_md[:2500]}

---

Ответь ТОЛЬКО валидным JSON объектом. Без markdown-блоков, без текста вне JSON.

Требования к форматированию поля instructions_md (это Markdown, который будет
отрендерен — соблюдай строго):
- Каждое задание начинай с заголовка ### и понятного названия.
- Стартовый код и решения — в fenced-блоках с указанием языка (```python, ```ts и т.п.).
- Условие давай блоками: строки «**Задача:** …», «**Артефакт:** …», «**Edge cases:** …».
- Решение/ответ оборачивай в сворачивалку: <details><summary>Решение</summary> … </details>.
  ВНУТРИ <details> оставляй пустую строку после <summary> и перед </details>, а код —
  в fenced-блоке с языком, иначе Markdown не отрендерится.

{{
  "learning_goals": [
    "Понять [ключевую концепцию 1] и объяснить своими словами",
    "Применить [концепцию 2] в реальном сценарии",
    "Разобрать типичные ошибки и как их избегать"
  ],
  "theory_task": {{
    "title": "Проверь себя: {topic_name}",
    "instructions_md": "# Проверь себя\\n\\nОтветь своими словами, не заглядывая в конспект:\\n\\n1. [Концептуальный вопрос — что происходит внутри и почему]\\n2. [Trade-off вопрос — когда работает, когда нет]\\n3. [Практический вопрос — что изменится если убрать/изменить X]\\n4. [Вопрос на связь с другими концепциями]\\n\\n<details><summary>Ответы</summary>\\n\\n**1.** [Ответ 1-2 предложения с объяснением почему]\\n\\n**2.** [Ответ]\\n\\n**3.** [Ответ]\\n\\n**4.** [Ответ]\\n\\n</details>\\n\\n---\\n\\n## Вопросы уровня собеседования\\n\\n**[Middle]** [Вопрос на механизм или поведение]\\n\\n<details><summary>Ответ</summary>\\n\\n[Ответ как дал бы сильный кандидат: факт + механизм + пример]\\n\\n</details>\\n\\n**[Senior]** [Вопрос на дизайн с нефункциональными требованиями]\\n\\n<details><summary>Ответ</summary>\\n\\n[Ответ с trade-offs и обоснованием]\\n\\n</details>"
  }},
  "mini_project_task": {{
    "title": "Практика: {topic_name}",
    "instructions_md": "# Практические задания\\n\\n## Уровень 1: База (5-10 мин)\\n\\n### Задание 1 (новичок)\\n\\n```python\\n# Стартовый код — скопируй и запусти как есть\\n# TODO: [конкретное однозначное действие]\\n```\\n\\n**Задача:** [глагол + что конкретно сделать]\\n\\n**Артефакт:** [что должен вывести или показать]\\n\\n<details><summary>Решение</summary>\\n\\n```python\\n# Решение:\\n# Вывод: [что напечатает]\\n```\\n\\n[1-2 предложения почему так]\\n\\n</details>\\n\\n### Задание 2 (новичок)\\n\\n[аналогично: заголовок, код, Задача, Артефакт, <details>Решение</details>]\\n\\n---\\n\\n## Уровень 2: Применение (20-35 мин)\\n\\n### Задание 3 (средний)\\n\\n```python\\n# Весь стартовый код — запускается без дополнений\\n# TODO: реализуй функцию ниже\\n```\\n\\n**Задача:** [реалистичный сценарий + конкретные требования]\\n\\n**Edge cases:** [2-3 случая которые решение обязано обработать]\\n\\n**Артефакт:** рабочий код + ожидаемый вывод\\n\\n<details><summary>Решение</summary>\\n\\n```python\\n# Решение + вывод:\\n```\\n\\n[Объяснение выбора]\\n\\n</details>\\n\\n---\\n\\n## Уровень 3: Собеседование (45+ мин)\\n\\n### Мини-проект / Capstone (Middle+/Senior)\\n\\n**Контекст:** [реалистичный production сценарий]\\n\\n**Задача:** [конкретное требование с ограничениями]\\n\\n**Acceptance checks:**\\n- [happy path]\\n- [edge case]\\n- [failure case]\\n\\n<details><summary>Разбор</summary>\\n\\n[Эталонное решение + типичные ошибки + альтернативы]\\n\\n</details>",
    "expected_evidence": ["source_files", "diff", "test_output", "reflection"],
    "target_concepts": ["концепт 1 из темы", "концепт 2 из темы"]
  }}
}}"""


# ── Streaming generation ───────────────────────────────────────────────────────

async def _prepare_materials_block(
    settings: Any, topic: TopicInfo, materials: list[dict], q: asyncio.Queue
) -> str:
    """Build the materials block for the conspect prompt.

    Small corpora go in whole. Large corpora are distilled via map-reduce so a big
    file actually informs the conspect instead of contributing only its first chunk.
    """
    from app.services.content_reduction import SINGLE_PASS_LIMIT, map_reduce_digest

    total_chars = sum(len(m.get("content_text", "")) for m in materials)
    if total_chars <= SINGLE_PASS_LIMIT:
        return "\n\n".join(
            f"--- Материал: {m['name']} ({m.get('type', 'material')}) ---\n{m['content_text']}"
            for m in materials
            if m.get("content_text")
        )

    await q.put(("phase_change", {"phase": "study", "label": "Изучаю материалы..."}))

    async def _progress(current: int, total: int) -> None:
        await q.put(("progress", {
            "phase": "study",
            "label": f"Изучаю материалы {current}/{total}...",
            "current": current,
            "total": total,
        }))

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        digest = await map_reduce_digest(
            client,
            settings,
            topic.name,
            [(m["name"], m["content_text"]) for m in materials if m.get("content_text")],
            progress=_progress,
        )
    return "## Выжимка концепций из материалов\n\n" + digest


async def stream_conspect_to_queue(
    settings: Any,
    topic: TopicInfo,
    materials: list[dict],
    q: asyncio.Queue,
) -> str:
    """Stream conspect tokens to SSE queue. Returns conspect_md."""
    materials_block = await _prepare_materials_block(settings, topic, materials, q)

    await q.put(("phase_change", {"phase": "conspect", "label": "Пишу конспект..."}))

    conspect_md = ""
    prompt_conspect = _build_conspect_prompt(topic.name, materials_block)

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        async for token in _llm_stream_tokens(
            client,
            settings,
            prompt_conspect,
            max_tokens=4000,
            system=CONSPECT_SYSTEM_PROMPT,
        ):
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
    # Brief pause to avoid hitting rate limits immediately after conspect streaming
    await asyncio.sleep(4)
    await q.put(("phase_change", {"phase": "tasks", "label": "Создаю задания..."}))

    prompt_tasks = _build_tasks_prompt(topic.name, conspect_md)

    async with httpx.AsyncClient(timeout=180.0) as client:
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
            f"# Практическое задание\n\n"
            f"## Задача\n\n"
            f"Создай небольшой проект или измени текущий, чтобы показать понимание темы "
            f"**{topic.name}**.\n\n"
            "**Задача:** реализуй рабочее решение, демонстрирующее ключевую концепцию темы.\n\n"
            "**Артефакт:** работающий код + краткое описание того, что он делает.\n\n"
            "## Что отправить\n\n"
            "- изменённые исходные файлы или diff;\n"
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
