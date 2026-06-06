from datetime import date, datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_streak import UserStreak, CardSession
from app.models.review_card import ReviewCard
from app.models import Capsule, ReviewQuestion, TopicCard


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


async def get_card_stats(db: AsyncSession, user_id: str, topic_id: str | None = None) -> dict:
    now = datetime.now(timezone.utc)
    today = date.today()

    # Due count spans BOTH card sources (capsule ReviewCards + TopicCards); optionally
    # scoped to one topic. ReviewCards reach the topic via ReviewQuestion→Capsule.
    rc_due = (
        select(func.count())
        .select_from(ReviewCard)
        .where(ReviewCard.user_id == user_id, ReviewCard.next_review_at <= now)
    )
    if topic_id:
        rc_due = (
            select(func.count())
            .select_from(ReviewCard)
            .join(ReviewQuestion, ReviewCard.question_id == ReviewQuestion.id)
            .join(Capsule, ReviewQuestion.capsule_id == Capsule.id)
            .where(
                ReviewCard.user_id == user_id,
                ReviewCard.next_review_at <= now,
                Capsule.topic_id == topic_id,
            )
        )
    tc_due = (
        select(func.count())
        .select_from(TopicCard)
        .where(TopicCard.user_id == user_id, TopicCard.next_review_at <= now)
    )
    if topic_id:
        tc_due = tc_due.where(TopicCard.topic_id == topic_id)

    due_today = ((await db.execute(rc_due)).scalar() or 0) + ((await db.execute(tc_due)).scalar() or 0)

    session_result = await db.execute(
        select(CardSession).where(CardSession.user_id == user_id, CardSession.session_date == today)
    )
    session = session_result.scalar_one_or_none()
    reviewed_today = session.cards_reviewed if session else 0

    streak = await get_or_create_streak(db, user_id)

    # Earliest upcoming review across both sources.
    rc_next_q = (
        select(ReviewCard.next_review_at)
        .where(ReviewCard.user_id == user_id, ReviewCard.next_review_at > now)
        .order_by(ReviewCard.next_review_at)
        .limit(1)
    )
    tc_next_q = (
        select(TopicCard.next_review_at)
        .where(TopicCard.user_id == user_id, TopicCard.next_review_at > now)
        .order_by(TopicCard.next_review_at)
        .limit(1)
    )
    if topic_id:
        rc_next_q = (
            select(ReviewCard.next_review_at)
            .join(ReviewQuestion, ReviewCard.question_id == ReviewQuestion.id)
            .join(Capsule, ReviewQuestion.capsule_id == Capsule.id)
            .where(
                ReviewCard.user_id == user_id,
                ReviewCard.next_review_at > now,
                Capsule.topic_id == topic_id,
            )
            .order_by(ReviewCard.next_review_at)
            .limit(1)
        )
        tc_next_q = tc_next_q.where(TopicCard.topic_id == topic_id)

    rc_next = (await db.execute(rc_next_q)).scalar_one_or_none()
    tc_next = (await db.execute(tc_next_q)).scalar_one_or_none()
    candidates = [d for d in (rc_next, tc_next) if d is not None]
    next_due_at = min(candidates) if candidates else None

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
