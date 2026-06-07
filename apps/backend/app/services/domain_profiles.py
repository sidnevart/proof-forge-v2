"""Domain profiles — the single place that encodes how a subject domain shapes
generation. A topic is classified into one domain at start (see domain_classifier);
the profile then parametrizes the conspect persona, which sections are appropriate,
whether code/diagrams belong, and the task recipe.

This is what makes "English needs no code; theory_math needs worked problems" a
data-driven decision instead of a hardcoded IT-mentor prompt.
"""
from dataclasses import dataclass, field

# Canonical domain labels. `general` is the safe fallback for anything unclassified.
DOMAINS = ("coding", "language", "theory_math", "humanities", "general")
DEFAULT_DOMAIN = "general"


@dataclass(frozen=True)
class TaskType:
    """One task the generator may emit for this domain.

    `key` is the PracticeTask.type stored in the DB. `coding`/`language`/etc. each
    pick a small recipe of task types instead of the universal theory+mini_project.
    """
    key: str
    title_hint: str
    instructions_hint: str
    expected_evidence: list[str] = field(default_factory=lambda: ["written_explanation"])
    difficulty: int = 1


@dataclass(frozen=True)
class DomainProfile:
    domain: str
    # Persona/system framing for the conspect writer.
    persona: str
    # One-line description of the learner audience, woven into prompts.
    audience: str
    # Whether fenced code blocks are appropriate in conspect & tasks.
    allow_code: bool
    # Whether Mermaid diagrams are appropriate.
    allow_diagrams: bool
    # Domain-appropriate conspect body sections (between Prerequisites and Glossary,
    # which are always present). Used to steer structure away from the IT default.
    conspect_sections: list[str]
    # The task recipe — what kinds of practice this domain produces.
    task_recipe: list[TaskType]
    # Short instruction appended to generation prompts to enforce domain norms.
    generation_note: str
    # Whether mathematical notation must be rendered as LaTeX ($...$ inline,
    # $$...$$ block). Enables the KaTeX-rendered formula path for technical domains.
    math_notation: bool = False


_CODING = DomainProfile(
    domain="coding",
    persona=(
        "Ты — сильный учебный ментор для разработчиков. Объясняешь глубоко, но «на "
        "пальцах»: каждую идею сопровождаешь аналогией, примером кода и, где уместно, схемой."
    ),
    audience="разработчики и инженеры",
    allow_code=True,
    allow_diagrams=True,
    conspect_sections=[
        "Ключевые концепции",
        "Как это работает шаг за шагом",
        "Сравнение подходов",
        "Практическое применение",
        "Типичные ошибки",
    ],
    task_recipe=[
        TaskType(
            key="theory",
            title_hint="Проверь себя",
            instructions_hint="8-12 вопросов по нарастающей: факты → механизм → trade-offs → edge cases",
            expected_evidence=["written_explanation"],
            difficulty=1,
        ),
        TaskType(
            key="mini_project",
            title_hint="Практика",
            instructions_hint="5 уровней сложности со стартовым кодом и разбором; уровень 5 — спроектировать или улучшить мини-систему",
            expected_evidence=["source_files", "diff", "test_output", "reflection"],
            difficulty=3,
        ),
    ],
    generation_note=(
        "Код — в fenced-блоках с языком. Минимум 1-2 Mermaid-диаграммы. "
        "Оценки сложности и любую математику пиши в LaTeX ($O(n\\log n)$, $\\Theta(1)$)."
    ),
    math_notation=True,
)

_LANGUAGE = DomainProfile(
    domain="language",
    persona=(
        "Ты — опытный преподаватель иностранных языков. Объясняешь правила просто, на "
        "живых примерах и мини-диалогах. НИКАКОГО программного кода — вместо него примеры "
        "фраз, таблицы спряжений/склонений и разбор употребления."
    ),
    audience="изучающие язык",
    allow_code=False,
    allow_diagrams=False,
    conspect_sections=[
        "Ключевые правила",
        "Примеры и употребление",
        "Мини-диалог",
        "Частые ошибки и ложные друзья",
    ],
    task_recipe=[
        TaskType(
            key="theory",
            title_hint="Грамматика и понимание",
            instructions_hint="8-12 вопросов по нарастающей: правила → употребление → нюансы → ложные друзья и edge cases",
            expected_evidence=["written_explanation"],
            difficulty=1,
        ),
        TaskType(
            key="written",
            title_hint="Практика языка",
            instructions_hint=(
                "5 уровней сложности: от подстановки до составления связного текста; "
                "уровень 5 — самостоятельный текст/диалог с разбором. Эталоны в <details>"
            ),
            expected_evidence=["written_explanation"],
            difficulty=3,
        ),
    ],
    generation_note="Без кода и без технических диаграмм. Примеры — фразы и таблицы форм.",
)

_THEORY_MATH = DomainProfile(
    domain="theory_math",
    persona=(
        "Ты — сильный преподаватель точных наук. Объясняешь интуицию за формулами, "
        "выводишь ключевые соотношения по шагам и показываешь разбор задач. "
        "ВСЕ формулы записываешь в LaTeX и никогда не теряешь математику темы."
    ),
    audience="изучающие математику и теоретические дисциплины",
    allow_code=False,
    allow_diagrams=True,
    conspect_sections=[
        "Ключевые понятия и определения",
        "Формулы и ключевые соотношения",
        "Интуиция и вывод формул",
        "Разбор задач шаг за шагом",
        "Типичные ошибки",
    ],
    task_recipe=[
        TaskType(
            key="theory",
            title_hint="Понимание теории",
            instructions_hint="8-12 вопросов по нарастающей: определения → интуиция → связи понятий → нетривиальные случаи",
            expected_evidence=["written_explanation"],
            difficulty=1,
        ),
        TaskType(
            key="written",
            title_hint="Решение задач",
            instructions_hint=(
                "5 уровней сложности с полным разбором в <details>; уровень 5 — "
                "комплексная задача/доказательство с обоснованием каждого шага"
            ),
            expected_evidence=["written_explanation"],
            difficulty=3,
        ),
    ],
    generation_note=(
        "ВСЕ формулы — ТОЛЬКО в LaTeX: $...$ инлайн, $$...$$ блочные. "
        "Обязательно приведи ключевые формулы темы и выведи важнейшие пошагово. "
        "Никогда не записывай формулы простым текстом или Unicode-символами. Без программного кода."
    ),
    math_notation=True,
)

_HUMANITIES = DomainProfile(
    domain="humanities",
    persona=(
        "Ты — вдумчивый преподаватель гуманитарных дисциплин. Объясняешь контекст, связи "
        "и аргументы, опираешься на примеры и источники, поощряешь критическое мышление."
    ),
    audience="изучающие гуманитарные дисциплины",
    allow_code=False,
    allow_diagrams=False,
    conspect_sections=[
        "Ключевые идеи и контекст",
        "Аргументы и трактовки",
        "Примеры и источники",
        "Спорные моменты",
    ],
    task_recipe=[
        TaskType(
            key="theory",
            title_hint="Проверь понимание",
            instructions_hint="8-12 вопросов по нарастающей: смысл → контекст → связи идей → спорные трактовки",
            expected_evidence=["written_explanation"],
            difficulty=1,
        ),
        TaskType(
            key="written",
            title_hint="Эссе и анализ",
            instructions_hint=(
                "5 уровней сложности: от короткого ответа до развёрнутого эссе/анализа источника; "
                "уровень 5 — самостоятельная аргументация с разбором сильного ответа в <details>"
            ),
            expected_evidence=["written_explanation"],
            difficulty=3,
        ),
    ],
    generation_note="Без кода и диаграмм. Опирайся на примеры, цитаты и контекст.",
)

_GENERAL = DomainProfile(
    domain="general",
    persona=(
        "Ты — сильный учебный ментор. Объясняешь глубоко, но «на пальцах»: каждую идею "
        "сопровождаешь аналогией и наглядным примером."
    ),
    audience="самостоятельные учащиеся",
    allow_code=True,
    allow_diagrams=True,
    conspect_sections=[
        "Ключевые концепции",
        "Как это работает",
        "Практическое применение",
        "Типичные ошибки",
    ],
    task_recipe=[
        TaskType(
            key="theory",
            title_hint="Проверь себя",
            instructions_hint="8-12 вопросов по нарастающей: факты → механизм → связи → нетривиальные случаи",
            expected_evidence=["written_explanation"],
            difficulty=1,
        ),
        TaskType(
            key="written",
            title_hint="Практика",
            instructions_hint="5 уровней сложности на применение с разбором в <details>; уровень 5 — комплексное задание",
            expected_evidence=["written_explanation"],
            difficulty=3,
        ),
    ],
    generation_note=(
        "Подбирай примеры под характер темы; код используй только если он уместен. "
        "Если в теме есть формулы — записывай их в LaTeX ($...$ / $$...$$)."
    ),
    math_notation=True,
)


_PROFILES: dict[str, DomainProfile] = {
    "coding": _CODING,
    "language": _LANGUAGE,
    "theory_math": _THEORY_MATH,
    "humanities": _HUMANITIES,
    "general": _GENERAL,
}


def get_profile(domain: str | None) -> DomainProfile:
    """Resolve a domain label to its profile, falling back to `general`."""
    return _PROFILES.get((domain or "").strip().lower(), _GENERAL)
