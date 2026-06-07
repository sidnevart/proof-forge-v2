"""Learning-strategy presets and config normalization.

A strategy is a small set of knobs that parametrize *how* a topic is taught —
orthogonal to the domain (which decides *what kinds* of content are valid). Domain
decides "code or no code"; strategy decides "how deep, how hard, how much practice".

Phase 1 (now): a manual constructor + named presets. Auto-recommendation from learner
history is deferred — see Workstream I (event logging) for the data groundwork.
"""
from dataclasses import dataclass, field

# Knob value vocabularies (kept as plain strings so they round-trip through JSON).
DEPTHS = ("brief", "moderate", "comprehensive")
RATIOS = ("theory_heavy", "balanced", "practice_heavy")
DIFFICULTIES = ("gentle", "standard", "challenging")
PACINGS = ("relaxed", "standard", "intensive")


@dataclass(frozen=True)
class StrategyConfig:
    depth: str = "comprehensive"          # conspect length / coverage
    theory_practice_ratio: str = "balanced"
    difficulty: str = "standard"
    pacing: str = "standard"
    include_diagrams: bool = True         # honored only when domain allows diagrams
    weak_spot_focus: bool = True          # emphasize known weak spots in tasks
    # ── StudyProfile signals (from the adaptive onboarding interview) ──────────
    # Empty/neutral by default so preset-only and Skip paths behave exactly as before.
    goal: str = ""                        # understand | refresh | interview | solve_task
    known_concepts: list = field(default_factory=list)   # compress (don't omit) in conspect
    focus_subtopics: list = field(default_factory=list)  # emphasize in conspect + tasks
    task_format: list = field(default_factory=list)      # learner-preferred task kinds

    def to_dict(self) -> dict:
        return {
            "depth": self.depth,
            "theory_practice_ratio": self.theory_practice_ratio,
            "difficulty": self.difficulty,
            "pacing": self.pacing,
            "include_diagrams": self.include_diagrams,
            "weak_spot_focus": self.weak_spot_focus,
            "goal": self.goal,
            "known_concepts": list(self.known_concepts),
            "focus_subtopics": list(self.focus_subtopics),
            "task_format": list(self.task_format),
        }


# Named presets surfaced in the topic-start UI. `deep_dive` is the default and is the
# closest match to the platform's pre-strategy behavior, so unset topics behave as before.
PRESETS: dict[str, StrategyConfig] = {
    "deep_dive": StrategyConfig(
        depth="comprehensive", theory_practice_ratio="balanced",
        difficulty="standard", pacing="standard",
        include_diagrams=True, weak_spot_focus=True,
    ),
    "practical_sprint": StrategyConfig(
        depth="moderate", theory_practice_ratio="practice_heavy",
        difficulty="challenging", pacing="intensive",
        include_diagrams=True, weak_spot_focus=True,
    ),
    "exam_cram": StrategyConfig(
        depth="brief", theory_practice_ratio="balanced",
        difficulty="challenging", pacing="intensive",
        include_diagrams=False, weak_spot_focus=True,
    ),
    "gentle_intro": StrategyConfig(
        depth="moderate", theory_practice_ratio="theory_heavy",
        difficulty="gentle", pacing="relaxed",
        include_diagrams=True, weak_spot_focus=False,
    ),
}

DEFAULT_PRESET = "deep_dive"

# Approx. conspect word-count windows per depth, fed into the conspect prompt.
_DEPTH_WORDS = {
    "brief": "900-1300 слов",
    "moderate": "1400-2000 слов",
    "comprehensive": "1800-2800 слов",
}

_RATIO_NOTE = {
    "theory_heavy": "Делай упор на теорию и понимание; практики меньше.",
    "balanced": "Балансируй теорию и практику примерно поровну.",
    "practice_heavy": "Делай упор на практику; теорию давай сжато, сразу к заданиям.",
}

_DIFFICULTY_NOTE = {
    "gentle": "Уровень — мягкий: начинай с азов, плавно повышай сложность, но в конце дай хотя бы одно по-настоящему сложное задание.",
    "standard": "Уровень — стандартный с запасом вверх: от базы к применению, обязательно с нетривиальными случаями и edge cases в конце.",
    "challenging": "Уровень — высокий, как на собеседовании Middle+/Senior: преобладают нетривиальные задачи, пограничные случаи, trade-offs и многошаговые рассуждения. Избегай простых вопросов на пересказ.",
}


def resolve_strategy(config: dict | None) -> StrategyConfig:
    """Resolve stored JSON (or None) to a StrategyConfig, defaulting to deep_dive.

    Accepts either a preset reference `{"preset": "exam_cram"}` or a full/partial knob
    dict. Unknown keys are ignored; missing knobs inherit the default preset.
    """
    base = PRESETS[DEFAULT_PRESET]
    if not config:
        return base

    if isinstance(config, dict) and config.get("preset") in PRESETS:
        base = PRESETS[config["preset"]]

    def pick(key: str, allowed: tuple, fallback):
        val = config.get(key) if isinstance(config, dict) else None
        return val if val in allowed else fallback

    def _str_list(key: str) -> list:
        val = config.get(key) if isinstance(config, dict) else None
        if isinstance(val, list):
            return [str(v).strip() for v in val if str(v).strip()]
        return []

    return StrategyConfig(
        depth=pick("depth", DEPTHS, base.depth),
        theory_practice_ratio=pick("theory_practice_ratio", RATIOS, base.theory_practice_ratio),
        difficulty=pick("difficulty", DIFFICULTIES, base.difficulty),
        pacing=pick("pacing", PACINGS, base.pacing),
        include_diagrams=bool(config.get("include_diagrams", base.include_diagrams))
        if isinstance(config, dict) else base.include_diagrams,
        weak_spot_focus=bool(config.get("weak_spot_focus", base.weak_spot_focus))
        if isinstance(config, dict) else base.weak_spot_focus,
        goal=str(config.get("goal", "")) if isinstance(config, dict) else "",
        known_concepts=_str_list("known_concepts"),
        focus_subtopics=_str_list("focus_subtopics"),
        task_format=_str_list("task_format"),
    )


def conspect_word_count(strategy: StrategyConfig) -> str:
    return _DEPTH_WORDS.get(strategy.depth, _DEPTH_WORDS["comprehensive"])


def strategy_generation_notes(strategy: StrategyConfig) -> str:
    """Compact human-readable steering appended to generation prompts."""
    parts = [
        _RATIO_NOTE.get(strategy.theory_practice_ratio, ""),
        _DIFFICULTY_NOTE.get(strategy.difficulty, ""),
    ]
    if strategy.weak_spot_focus:
        parts.append("Если известны слабые места ученика — делай на них акцент.")
    return " ".join(p for p in parts if p)


_GOAL_NOTE = {
    "understand": "Цель ученика — понять тему с нуля; не предполагай предварительных знаний сверх пререквизитов.",
    "refresh": "Цель ученика — освежить уже знакомую тему; будь сжатым, фокусируйся на ключевом и нюансах.",
    "interview": "Цель ученика — подготовка к собеседованию; добавляй вопросы на механизм, trade-offs и edge cases.",
    "solve_task": "Цель ученика — решить конкретную практическую задачу; делай упор на применимость.",
}


def profile_generation_notes(strategy: StrategyConfig) -> str:
    """Render the StudyProfile signals (goal/known/focus) into prompt lines.

    Empty when no profile signals are set, so preset-only and Skip paths are unaffected.
    """
    lines: list[str] = []
    if strategy.goal and strategy.goal in _GOAL_NOTE:
        lines.append(_GOAL_NOTE[strategy.goal])
    if strategy.known_concepts:
        lines.append(
            "Ученик уже владеет: " + ", ".join(strategy.known_concepts)
            + " — упомяни кратко, не разжёвывай (но не выкидывай из структуры)."
        )
    if strategy.focus_subtopics:
        lines.append("Сделай акцент на: " + ", ".join(strategy.focus_subtopics) + ".")
    return "\n".join(lines)
