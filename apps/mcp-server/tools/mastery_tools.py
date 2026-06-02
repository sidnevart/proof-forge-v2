from client import post, get
from session import get_uid


async def record_mastery(
    topic_id: str,
    concept: str,
    kind: str,
    difficulty: int = 0,
    quality_score: float = 0.0,
    struggle_passed: int = 0,
    user_id: str = "",
) -> dict:
    """Record a theory or practice rep for a concept — drives mastery tracking.
    kind: 'theory' (concept explained) or 'practice' (task completed).
    For practice pass difficulty (1-3), quality_score (0-1), struggle_passed (0/1).
    Call after every explanation and every completed practice task."""
    return await post("/api/mastery/record", {
        "user_id": await get_uid(user_id),
        "topic_id": topic_id,
        "concept": concept,
        "kind": kind,
        "difficulty": difficulty,
        "quality_score": quality_score,
        "struggle_passed": struggle_passed,
    })


async def get_mastery_progress(topic: str = "", user_id: str = "") -> dict:
    """Get mastery progress — per-concept badges (🟥🟨🟩🟦) + rollup (what blocks expert).
    Call when user asks 'прогресс', 'сколько я отработал', 'далеко ли до эксперта'."""
    params = {"userId": await get_uid(user_id)}
    if topic:
        params["topic"] = topic
    return await get("/api/mastery/progress", params)


async def get_next_focus(topic: str = "", user_id: str = "") -> dict:
    """Get the concept that needs the most work next (lowest mastery / least practice)."""
    params = {"userId": await get_uid(user_id)}
    if topic:
        params["topic"] = topic
    return await get("/api/mastery/next", params)
