from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConceptMastery


def compute_level(m: ConceptMastery) -> str:
    """Deterministic mastery level from reps/quality/difficulty. No LLM."""
    if m.theory_reps == 0 and m.practice_reps == 0:
        return "unknown"
    if (
        m.practice_reps >= 3
        and m.practice_quality >= 0.8
        and m.max_difficulty >= 3
        and m.struggle_passed >= 1
    ):
        return "explain"
    if m.practice_reps >= 2 and m.practice_quality >= 0.6 and m.max_difficulty >= 2:
        return "apply"
    if m.theory_reps >= 1:
        return "recognize"
    return "recognize"


BADGE = {"unknown": "🟥", "recognize": "🟨", "apply": "🟩", "explain": "🟦"}


async def record(
    db: AsyncSession,
    user_id: str,
    topic_id: str,
    concept: str,
    kind: str,
    difficulty: int = 0,
    quality_score: float = 0.0,
    struggle_passed: int = 0,
) -> ConceptMastery:
    result = await db.execute(
        select(ConceptMastery).where(
            ConceptMastery.user_id == user_id,
            ConceptMastery.topic_id == topic_id,
            ConceptMastery.concept == concept,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        m = ConceptMastery(
            user_id=user_id,
            topic_id=topic_id,
            concept=concept,
            theory_reps=0,
            practice_reps=0,
            practice_quality=0.0,
            max_difficulty=0,
            struggle_passed=0,
            mastery_level="unknown",
        )
        db.add(m)

    if kind == "theory":
        m.theory_reps += 1
    elif kind == "practice":
        # rolling average of quality across practice reps
        total = m.practice_quality * m.practice_reps + quality_score
        m.practice_reps += 1
        m.practice_quality = round(total / m.practice_reps, 4)
        m.max_difficulty = max(m.max_difficulty, difficulty)
        m.struggle_passed += max(0, struggle_passed)
        m.last_practiced_at = datetime.now(timezone.utc)

    m.mastery_level = compute_level(m)
    await db.commit()
    await db.refresh(m)
    return m


async def get_progress(db: AsyncSession, user_id: str, topic_id: str | None = None) -> dict:
    q = select(ConceptMastery).where(ConceptMastery.user_id == user_id)
    if topic_id:
        q = q.where(ConceptMastery.topic_id == topic_id)
    result = await db.execute(q.order_by(ConceptMastery.mastery_level, ConceptMastery.concept))
    rows = list(result.scalars().all())

    concepts = [
        {
            "concept": m.concept,
            "topic_id": m.topic_id,
            "mastery_level": m.mastery_level,
            "badge": BADGE.get(m.mastery_level, "🟥"),
            "theory_reps": m.theory_reps,
            "practice_reps": m.practice_reps,
            "practice_quality": m.practice_quality,
            "max_difficulty": m.max_difficulty,
            "struggle_passed": m.struggle_passed,
        }
        for m in rows
    ]

    total = len(rows)
    apply_plus = sum(1 for m in rows if m.mastery_level in ("apply", "explain"))
    expert = sum(1 for m in rows if m.mastery_level == "explain")
    total_practice = sum(m.practice_reps for m in rows)
    avg_quality = round(sum(m.practice_quality for m in rows) / total, 4) if total else 0.0

    # what blocks expert: concepts not yet at "explain"
    blocking = [
        {"concept": m.concept, "level": m.mastery_level, "badge": BADGE.get(m.mastery_level, "🟥")}
        for m in rows
        if m.mastery_level != "explain"
    ]

    return {
        "concepts": concepts,
        "rollup": {
            "total_concepts": total,
            "apply_plus": apply_plus,
            "expert": expert,
            "apply_plus_pct": round(apply_plus / total * 100, 1) if total else 0.0,
            "total_practice_reps": total_practice,
            "avg_quality": avg_quality,
            "blocking_expert": blocking,
        },
    }


async def get_next_focus(db: AsyncSession, user_id: str, topic_id: str | None = None) -> dict | None:
    q = select(ConceptMastery).where(ConceptMastery.user_id == user_id)
    if topic_id:
        q = q.where(ConceptMastery.topic_id == topic_id)
    result = await db.execute(q)
    rows = list(result.scalars().all())
    if not rows:
        return None

    # priority: lowest mastery level, then least practice
    order = {"unknown": 0, "recognize": 1, "apply": 2, "explain": 3}
    rows.sort(key=lambda m: (order.get(m.mastery_level, 0), m.practice_reps))
    m = rows[0]
    return {
        "concept": m.concept,
        "topic_id": m.topic_id,
        "mastery_level": m.mastery_level,
        "badge": BADGE.get(m.mastery_level, "🟥"),
        "practice_reps": m.practice_reps,
        "reason": _focus_reason(m),
    }


def _focus_reason(m: ConceptMastery) -> str:
    if m.mastery_level == "unknown":
        return "ещё не начат — начни с теории"
    if m.mastery_level == "recognize":
        return "теория есть, нужна практика (минимум 2 задания уровня apply)"
    if m.mastery_level == "apply":
        return "нужны задания сложнее (difficulty 3) + struggle-check для уровня explain"
    return "освоен на explain 🟦"
