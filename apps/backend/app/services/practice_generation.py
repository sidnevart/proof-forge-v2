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
    # Subject domain + learner strategy, resolved at session start. Drive the
    # conspect/task prompts via domain_profiles + strategy_presets. Defaults keep
    # the LLM-less fallback path (tests) behaving exactly as before.
    domain: str = "general"
    strategy_config: dict | None = None


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

# Backward-compatible default system prompt (coding persona). The adaptive,
# domain-aware system prompt is built by build_conspect_system() below.
CONSPECT_SYSTEM_PROMPT = (
    "Ты — сильный учебный ментор для IT-специалистов. Объясняешь глубоко, но «на пальцах»: "
    "каждую идею сопровождаешь бытовой аналогией, наглядным примером и, где уместно, схемой. "
    "Принцип подачи: наблюдение → гипотеза → эксперимент → решение."
)


def build_conspect_system(profile, strategy) -> str:
    """Domain- and strategy-aware system prompt for the conspect writer."""
    from app.services.strategy_presets import profile_generation_notes, strategy_generation_notes

    code_rule = (
        "- Код — в fenced-блоках с языком (```python, ```ts и т.п.).\n"
        if profile.allow_code
        else "- НЕ используй программный код — он не нужен в этой теме. Примеры давай словами.\n"
    )
    diagram_rule = (
        "- Для процессов/архитектур — диаграмма Mermaid в fenced-блоке ```mermaid "
        "(flowchart TD / sequenceDiagram). 1-2 диаграммы на конспект.\n"
        if (profile.allow_diagrams and strategy.include_diagrams)
        else ""
    )
    math_rule = (
        "- Любые формулы и математику пиши ТОЛЬКО в LaTeX: `$...$` инлайн (напр. $O(n\\log n)$, "
        "$P(A\\mid B)$), `$$...$$` для отдельных формул. НИКОГДА не записывай формулы простым "
        "текстом, Unicode-символами (∑, √, ≤) или внутри код-блоков.\n"
        if getattr(profile, "math_notation", False)
        else ""
    )
    return (
        f"{profile.persona}\n\n"
        "Форматирование (строго соблюдай — это влияет на читаемость):\n"
        "- Чёткая иерархия заголовков: ## для секций, ### для подсекций. "
        "НИКОГДА не ставь два заголовка подряд без текста между ними.\n"
        "- Каждый параграф — 2-4 предложения, разделяй пустой строкой. Никаких «стен текста».\n"
        "- Основные секции разделяй горизонтальной чертой `---`.\n"
        "- Для списков — маркированные списки, не плотный текст.\n"
        "- **Жирным** выделяй ключевые термины при первом упоминании.\n"
        "- Для сравнений (подходы, trade-offs) — Markdown-таблица. Перед таблицей и после неё "
        "обязательно пустая строка; таблица не шире 3-4 столбцов, ячейки краткие (без переносов строк внутри ячейки).\n"
        f"{code_rule}"
        f"{diagram_rule}"
        f"{math_rule}"
        "- Не оставляй HTML-теги кроме обычного Markdown.\n"
        f"{profile.generation_note}\n"
        f"{strategy_generation_notes(strategy)}\n"
        f"{profile_generation_notes(strategy)}\n"
        "Язык: русский, термины — на языке оригинала."
    )


def _conspect_body_sections(profile, strategy) -> str:
    """Assemble the domain-specific middle sections of the conspect template."""
    code_hint = ", короткий пример кода" if profile.allow_code else ", пример словами"
    blocks: list[str] = []
    for section in profile.conspect_sections:
        low = section.lower()
        if "ошибк" in low or "ловушк" in low or "спорн" in low:
            if profile.allow_code:
                guidance = (
                    "### Ошибка 1: [название]\n"
                    "❌ Неправильно:\n```[lang]\n[код с ошибкой]\n```\n"
                    "✅ Правильно:\n```[lang]\n[исправленный код]\n```\n"
                    "[1-2 предложения: почему так и как избежать.]\n\n"
                    "### Ошибка 2: [аналогично]\n[2-3 ошибки, каждая с ### заголовком.]"
                )
            else:
                guidance = (
                    "[2-3 типичные ошибки/заблуждения. Каждая — ### подзаголовок, "
                    "затем «❌ Неправильно … ✅ Правильно …» словами и почему так.]"
                )
        elif "концеп" in low or "правил" in low or "понят" in low or "иде" in low:
            guidance = (
                "### [Название 1]\n[1-2 абзаца простыми словами.]\n\n"
                "**Аналогия на пальцах:** [коротко]\n\n"
                f"[наглядный пример{code_hint}]\n\n"
                "### [Название 2]\n[аналогично]\n\n"
                "[3-5 пунктов, каждый с ### заголовком. Не сливай в один текст.]"
            )
        elif "соотношен" in low:
            guidance = (
                "[Сведи КЛЮЧЕВЫЕ формулы темы в этот раздел. Каждую крупную формулу — отдельной "
                "строкой в блочном LaTeX `$$...$$`, сразу под ней расшифруй обозначения. Затем "
                "выведи 1-2 важнейшие формулы пошагово (каждый шаг — `$$...$$` с пояснением). "
                "Не пропускай формулы темы и не записывай их простым текстом.]"
            )
        elif "сравн" in low:
            guidance = "[Markdown-таблица: вариант / когда использовать / плюсы / минусы.]"
        elif "диалог" in low:
            guidance = "[Короткий диалог из 4-6 реплик с переводом каждой реплики.]"
        else:
            guidance = (
                f"[Раскрой раздел применительно к теме: 2-4 абзаца, наглядные примеры{code_hint}. "
                "Если есть последовательность шагов — нумерованный список.]"
            )
        blocks.append(f"## {section}\n{guidance}")
    return "\n\n---\n\n".join(blocks)


def _build_conspect_prompt(topic_name: str, materials_block: str, profile, strategy) -> str:
    from app.services.strategy_presets import conspect_word_count

    if not materials_block.strip():
        materials_block = "(материалов нет — используй свои знания о теме)"

    word_count = conspect_word_count(strategy)
    diagram_line = (
        "\n```mermaid\nflowchart TD\n  [Схема общей картины темы]\n```\n"
        if (profile.allow_diagrams and strategy.include_diagrams)
        else ""
    )
    body = _conspect_body_sections(profile, strategy)

    return f"""На основе материалов по теме «{topic_name}» напиши подробный, наглядный конспект для аудитории «{profile.audience}».

## Материалы
{materials_block}

---

Напиши конспект в формате Markdown ({word_count}). Объясняй «на пальцах», не экономь на примерах.

**Структура конспекта (строго в этом порядке):**

## Обзор
[3-4 предложения: что это, зачем нужно и какую проблему решает. Один абзац.]

**Аналогия на пальцах:** [бытовой образ в 1-2 предложениях.]
{diagram_line}
---

## Пререквизиты
[Что полезно знать ДО изучения этой темы, чтобы идти спокойно. Маркированный список из 3-6 пунктов в формате «**Понятие** — зачем оно здесь». Если тема предполагает базовый уровень (напр. язык — A2/B1) — укажи его одной строкой.]

---

{body}

---

## Глоссарий
[Markdown-таблица ключевых терминов и аббревиатур этой темы: столбцы «Термин» и «Определение». 6-12 строк, краткие определения в одно предложение. Включай сокращения с расшифровкой.]

---

## Важно запомнить
- [Ключевой тезис 1 — одно предложение]
- [4-6 тезисов маркированным списком]

Начинай сразу с конспекта, без предисловий."""


def _build_tasks_prompt(topic_name: str, conspect_md: str, profile, strategy) -> str:
    from app.services.strategy_presets import profile_generation_notes, strategy_generation_notes

    theory_spec = profile.task_recipe[0]
    practice_spec = profile.task_recipe[1] if len(profile.task_recipe) > 1 else profile.task_recipe[0]

    code_rule = (
        "- Стартовый код и решения — в fenced-блоках с языком (```python, ```ts и т.п.). "
        "Код должен быть настоящим и осмысленным, без заглушек «...»."
        if profile.allow_code
        else "- НЕ используй программный код. Задания — текстовые/практические по сути темы."
    )
    math_rule = (
        "\n- Любые формулы в условиях и решениях — ТОЛЬКО в LaTeX ($...$ инлайн, $$...$$ блочные), "
        "никогда простым текстом или Unicode-символами."
        if getattr(profile, "math_notation", False)
        else ""
    )

    # Level 5 adapts to the domain: a coding topic gets a "design or improve a mini-system"
    # capstone; non-code domains get the hardest domain-appropriate equivalent.
    level5 = (
        "спроектировать небольшую систему С НУЛЯ ИЛИ внести изменения в предложенную систему и "
        "улучшить её — с продуманной архитектурой, рабочим кодом и обоснованием trade-offs"
        if profile.allow_code
        else "комплексное самостоятельное задание: развёрнутый разбор/эссе/полное решение "
        "с обоснованием каждого шага и разбором альтернатив"
    )

    return f"""На основе конспекта по теме «{topic_name}» создай учебные задания для аудитории «{profile.audience}».
Задания должны быть ДЕЙСТВИТЕЛЬНО сложными и заставлять думать, а не пересказывать конспект. Минимум треть заданий — уровня технического собеседования Middle+/Senior (нетривиальный ход мысли, пограничные случаи, trade-offs). Не повторяй формулировки конспекта дословно. Опирайся на конкретику темы, а не на общие фразы.

## Конспект
{conspect_md[:12000]}

---

{strategy_generation_notes(strategy)}
{profile_generation_notes(strategy)}

Ответь ТОЛЬКО валидным JSON объектом. Без markdown-блоков, без текста вне JSON.

Требования к форматированию полей instructions_md (это Markdown, который будет отрендерен):
- Каждый блок начинай с заголовка ### и понятного названия.
{code_rule}{math_rule}
- Условие давай блоками: «**Задача:** …», и где уместно «**Что проверяется:** …», «**Edge cases:** …».
- Решение/ответ оборачивай в сворачивалку: <details><summary>Решение</summary> … </details>.
  ВНУТРИ <details> оставляй пустую строку после <summary> и перед </details>.
- Перед таблицей и после неё — пустая строка; таблицы не шире 3-4 столбцов.

{{
  "learning_goals": [
    "Понять механизм [ключевой идеи 1] и объяснить его своими словами",
    "Применить [идею 2] в нетривиальном случае",
    "Разобрать trade-offs и типичные ошибки"
  ],
  "theory_task": {{
    "title": "{theory_spec.title_hint}: {topic_name}",
    "instructions_md": "Глубокая проверка понимания: 8-12 вопросов СТРОГО по нарастающей сложности. Первые 2-3 — на факты и определения; затем на МЕХАНИЗМ («почему и как именно это работает»); затем на TRADE-OFFS и сравнение подходов; последние 2-3 — на EDGE CASES и нетривиальные ситуации. Каждый вопрос оформи как «### Вопрос N — <короткая суть>», под ним эталонный ответ в <details><summary>Ответ</summary> … </details> с пояснением ПОЧЕМУ так, а не просто «что». Вопросы конкретные по теме «{topic_name}», без воды."
  }},
  "practice_task": {{
    "title": "{practice_spec.title_hint}: {topic_name}",
    "instructions_md": "Практика из РОВНО 5 уровней сложности по нарастающей. Каждый уровень — отдельный заголовок вида «### Уровень N — <название>». Уровень 1 (лёгкий): прямое применение одной концепции. Уровень 2 (чуть сложнее): применение с небольшим усложнением. Уровень 3 (средний): комбинация нескольких концепций темы. Уровень 4 (выше среднего): нужен нетривиальный ход мысли, есть подвох или пограничный случай. Уровень 5 (сложный, надо хорошо подумать): {level5}. У КАЖДОГО уровня — блок «**Задача:** …», понятное условие и подробное эталонное решение/ответ в <details><summary>Решение</summary> … </details>. Уровни не должны дублировать друг друга по сложности.",
    "target_concepts": ["ключевой концепт 1 из темы", "ключевой концепт 2 из темы"]
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
    from app.services.domain_profiles import get_profile
    from app.services.strategy_presets import resolve_strategy

    profile = get_profile(topic.domain)
    strategy = resolve_strategy(topic.strategy_config)

    materials_block = await _prepare_materials_block(settings, topic, materials, q)

    await q.put(("phase_change", {"phase": "conspect", "label": "Пишу конспект..."}))

    conspect_md = ""
    prompt_conspect = _build_conspect_prompt(topic.name, materials_block, profile, strategy)
    system_prompt = build_conspect_system(profile, strategy)

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        async for token in _llm_stream_tokens(
            client,
            settings,
            prompt_conspect,
            max_tokens=8000,
            system=system_prompt,
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
    """Generate tasks from conspect. Returns (learning_goals, task_creates).

    Task types follow the topic's domain recipe (e.g. coding → theory + mini_project;
    language/humanities → theory + written), so an English topic never gets a
    "Python starter code" mini-project.
    """
    from app.services.domain_profiles import get_profile
    from app.services.strategy_presets import resolve_strategy

    profile = get_profile(topic.domain)
    strategy = resolve_strategy(topic.strategy_config)

    theory_spec = profile.task_recipe[0]
    practice_spec = profile.task_recipe[1] if len(profile.task_recipe) > 1 else profile.task_recipe[0]

    # Brief pause to avoid hitting rate limits immediately after conspect streaming
    await asyncio.sleep(4)
    await q.put(("phase_change", {"phase": "tasks", "label": "Создаю задания..."}))

    prompt_tasks = _build_tasks_prompt(topic.name, conspect_md, profile, strategy)

    async with httpx.AsyncClient(timeout=180.0) as client:
        raw = await _llm_call(
            client,
            settings,
            prompt_tasks,
            # 8-12 theory questions + 5 graded practice levels, each with a full worked
            # solution in <details>, needs substantially more room than the old 2-task set.
            max_tokens=8000,
            temperature=0.1,
            system="You are a JSON-only API. Output ONLY the JSON object, no preamble, no markdown fences, no explanations.",
        )
        parsed = _extract_json(raw)

    theory_raw = parsed.get("theory_task", {})
    # The practice task key is "practice_task" in the current schema; accept the legacy
    # "mini_project_task" key too for forward/backward compatibility.
    practice_raw = parsed.get("practice_task") or parsed.get("mini_project_task", {})

    theory = PracticeTaskCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        study_session_id="",
        type=theory_spec.key,
        title=theory_raw.get("title", f"{theory_spec.title_hint}: {topic.name}"),
        instructions_md=theory_raw.get(
            "instructions_md",
            f"## {theory_spec.title_hint}: {topic.name}\n\nРазбери ключевые идеи из конспекта.",
        ),
        target_concepts=[topic.name],
        difficulty=theory_spec.difficulty,
        expected_evidence=list(theory_spec.expected_evidence),
        check_commands=[],
    )

    practice = PracticeTaskCreate(
        user_id=topic.user_id,
        topic_id=topic.id,
        study_session_id="",
        type=practice_spec.key,
        title=practice_raw.get("title", f"{practice_spec.title_hint}: {topic.name}"),
        instructions_md=practice_raw.get(
            "instructions_md",
            f"## {practice_spec.title_hint}\n\nВыполни практическое задание по теме {topic.name}.",
        ),
        target_concepts=practice_raw.get("target_concepts", [topic.name]),
        difficulty=practice_spec.difficulty,
        expected_evidence=practice_raw.get(
            "expected_evidence", list(practice_spec.expected_evidence)
        ),
        check_commands=[],
    )

    learning_goals = parsed.get("learning_goals", [f"Изучить {topic.name}"])
    return learning_goals, [theory, practice]


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
