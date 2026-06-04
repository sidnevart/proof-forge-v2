from datetime import date, datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_streak import UserStreak, CardSession
from app.models.review_card import ReviewCard


async def get_or_create_streak(db: AsyncSession, user_id: str) -> UserStreak:
    result = await db.execute(select(UserStreak).where(UserStreak.user_id == user_id))
    streak = result.scalar_one_or_none()
    if not streak:
        streak = UserStreak(user_id=user_id)
        db.add(streak)
        await db.commit()
        await db.refresh(streak)
    return streak


async def update_streak_after_review(db: AsyncSession, user_id: str) -> UserStreak:
    streak = await get_or_create_streak(db, user_id)
    today = date.today()

    if streak.last_review_date == today:
        return streak  # already counted today

    yesterday = date.fromordinal(today.toordinal() - 1)
    if streak.last_review_date == yesterday:
        streak.current_streak += 1
    else:
        streak.current_streak = 1

    streak.longest_streak = max(streak.longest_streak, streak.current_streak)
    streak.last_review_date = today
    streak.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(streak)
    return streak


async def get_card_stats(db: AsyncSession, user_id: str) -> dict:
    now = datetime.now(timezone.utc)
    today = date.today()

    due_result = await db.execute(
        select(func.count()).where(ReviewCard.user_id == user_id, ReviewCard.next_review_at <= now)
    )
    due_today = due_result.scalar() or 0

    session_result = await db.execute(
        select(CardSession).where(CardSession.user_id == user_id, CardSession.session_date == today)
    )
    session = session_result.scalar_one_or_none()
    reviewed_today = session.cards_reviewed if session else 0

    streak = await get_or_create_streak(db, user_id)

    next_due_result = await db.execute(
        select(ReviewCard.next_review_at)
        .where(ReviewCard.user_id == user_id, ReviewCard.next_review_at > now)
        .order_by(ReviewCard.next_review_at)
        .limit(1)
    )
    next_due_at = next_due_result.scalar_one_or_none()

    return {
        "due_today": due_today,
        "reviewed_today": reviewed_today,
        "streak": streak.current_streak,
        "longest_streak": streak.longest_streak,
        "next_due_at": next_due_at,
    }


async def record_card_session(db: AsyncSession, user_id: str, rating: int) -> None:
    today = date.today()
    result = await db.execute(
        select(CardSession).where(CardSession.user_id == user_id, CardSession.session_date == today)
    )
    session = result.scalar_one_or_none()
    if session:
        total_ratings = session.avg_rating * session.cards_reviewed + rating
        session.cards_reviewed += 1
        session.avg_rating = total_ratings / session.cards_reviewed
    else:
        session = CardSession(user_id=user_id, session_date=today, cards_reviewed=1, avg_rating=float(rating))
        db.add(session)
    await db.commit()
