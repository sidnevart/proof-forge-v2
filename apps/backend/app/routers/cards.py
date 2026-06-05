from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import review_card_repo, streak_repo
from app.schemas.card import CardFromCapsuleCreate, CardFromCapsuleOut, DueCardOut, CardAttemptCreate, CardAttemptOut
from app.schemas.streak import CardStatsOut, StreakOut

router = APIRouter(tags=["cards"])


@router.post("/cards/from-capsule", response_model=CardFromCapsuleOut, status_code=201)
async def create_cards_from_capsule(data: CardFromCapsuleCreate, db: AsyncSession = Depends(get_db)):
    created = await review_card_repo.create_cards_from_capsule(db, data.user_id, data.capsule_id)
    return CardFromCapsuleOut(created=created)


@router.get("/cards/due", response_model=list[DueCardOut])
async def get_due_cards(
    userId: str = Query(...),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    cards = await review_card_repo.get_due_cards(db, userId, limit)
    return [DueCardOut(**c) for c in cards]


@router.post("/cards/{card_id}/attempt", response_model=CardAttemptOut)
async def log_card_attempt(card_id: str, data: CardAttemptCreate, db: AsyncSession = Depends(get_db)):
    if data.rating not in (1, 2, 3, 4):
        raise HTTPException(status_code=422, detail="rating must be 1-4")
    card = await review_card_repo.log_card_attempt(db, card_id, data.user_id, data.rating, data.user_answer)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    await streak_repo.update_streak_after_review(db, data.user_id)
    await streak_repo.record_card_session(db, data.user_id, data.rating)
    return CardAttemptOut(
        card_id=card.id,
        next_review_at=card.next_review_at,
        interval_days=card.interval_days,
        ease_factor=card.ease_factor,
    )


@router.post("/cards/topic/{card_id}/attempt", response_model=CardAttemptOut)
async def log_topic_card_attempt(card_id: str, data: CardAttemptCreate, db: AsyncSession = Depends(get_db)):
    if data.rating not in (1, 2, 3, 4):
        raise HTTPException(status_code=422, detail="rating must be 1-4")
    card = await review_card_repo.log_topic_card_attempt(db, card_id, data.user_id, data.rating)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    await streak_repo.update_streak_after_review(db, data.user_id)
    await streak_repo.record_card_session(db, data.user_id, data.rating)
    return CardAttemptOut(
        card_id=card.id,
        next_review_at=card.next_review_at,
        interval_days=card.interval_days,
        ease_factor=card.ease_factor,
    )


@router.get("/cards/stats", response_model=CardStatsOut)
async def get_card_stats(userId: str = Query(...), db: AsyncSession = Depends(get_db)):
    stats = await streak_repo.get_card_stats(db, userId)
    return CardStatsOut(**stats)


@router.get("/cards/streak", response_model=StreakOut)
async def get_streak(userId: str = Query(...), db: AsyncSession = Depends(get_db)):
    streak = await streak_repo.get_or_create_streak(db, userId)
    return StreakOut.model_validate(streak)
