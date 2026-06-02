from client import post, get
from session import get_uid


async def create_cards_from_capsule(capsule_id: str, user_id: str = "") -> dict:
    """Create spaced-repetition cards from a capsule's review questions. Call after store_capsule."""
    return await post("/api/cards/from-capsule", {"user_id": await get_uid(user_id), "capsule_id": capsule_id})


async def get_due_cards(limit: int = 10, user_id: str = "") -> dict:
    """Get cards due for review today. Call when user says 'карточки', 'daily review', 'anki'."""
    return await get("/api/cards/due", {"userId": await get_uid(user_id), "limit": limit})


async def log_card_attempt(card_id: str, rating: int, user_answer: str, user_id: str = "") -> dict:
    """Log a card review attempt and update SM-2 interval. rating: 1=Again 2=Hard 3=Good 4=Easy."""
    return await post(f"/api/cards/{card_id}/attempt", {
        "user_id": await get_uid(user_id),
        "rating": rating,
        "user_answer": user_answer,
    })
