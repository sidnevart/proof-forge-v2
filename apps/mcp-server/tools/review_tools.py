from client import post
from session import get_uid


async def store_review_answer(
    question_id: str,
    user_answer: str,
    score: float,
    feedback: str,
    is_weak_spot: bool = False,
    user_id: str = "",
) -> dict:
    """Store a review answer evaluated by the agent. Returns {attempt_id}."""
    return await post("/api/reviews/answer", {
        "user_id": await get_uid(user_id),
        "question_id": question_id,
        "user_answer": user_answer,
        "score": score,
        "feedback": feedback,
        "is_weak_spot": is_weak_spot,
    })
