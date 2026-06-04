"""Business metrics aggregation endpoints."""
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, distinct, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.capsule import Capsule
from app.models.learning_event import LearningEvent
from app.models.user_streak import UserStreak, CardSession
from app.models.llm_usage_log import LlmUsageLog
from app.models.topic import Topic

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


# ── Overview ─────────────────────────────────────────────────────────────────

@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    today = _today_utc()
    yesterday = today - timedelta(days=1)
    week_ago = _days_ago(7)
    month_ago = _days_ago(30)

    # DAU — users with card session today
    dau_r = await db.execute(
        select(func.count(distinct(CardSession.user_id)))
        .where(CardSession.session_date == today)
    )
    dau = dau_r.scalar() or 0

    # DAU yesterday (for comparison)
    dau_yd_r = await db.execute(
        select(func.count(distinct(CardSession.user_id)))
        .where(CardSession.session_date == yesterday)
    )
    dau_yd = dau_yd_r.scalar() or 0

    # MAU — unique users with any event in last 30d
    mau_r = await db.execute(
        select(func.count(distinct(LearningEvent.user_id)))
        .where(LearningEvent.occurred_at >= month_ago)
    )
    mau = mau_r.scalar() or 0

    # New users today / 7d
    new_today_r = await db.execute(
        select(func.count(User.id))
        .where(func.date(User.created_at) == today)
    )
    new_today = new_today_r.scalar() or 0

    new_7d_r = await db.execute(
        select(func.count(User.id))
        .where(User.created_at >= week_ago)
    )
    new_7d = new_7d_r.scalar() or 0

    # Total users
    total_users_r = await db.execute(select(func.count(User.id)))
    total_users = total_users_r.scalar() or 0

    # Capsules generated today / 7d
    caps_today_r = await db.execute(
        select(func.count(Capsule.id))
        .where(func.date(Capsule.created_at) == today)
    )
    caps_today = caps_today_r.scalar() or 0

    caps_7d_r = await db.execute(
        select(func.count(Capsule.id))
        .where(Capsule.created_at >= week_ago)
    )
    caps_7d = caps_7d_r.scalar() or 0

    # Cards reviewed today
    cards_today_r = await db.execute(
        select(func.coalesce(func.sum(CardSession.cards_reviewed), 0))
        .where(CardSession.session_date == today)
    )
    cards_today = cards_today_r.scalar() or 0

    # AI cost today / 7d
    ai_today_r = await db.execute(
        select(func.coalesce(func.sum(LlmUsageLog.cost_usd), 0.0))
        .where(func.date(LlmUsageLog.created_at) == today)
    )
    ai_cost_today = round(float(ai_today_r.scalar() or 0), 6)

    ai_7d_r = await db.execute(
        select(func.coalesce(func.sum(LlmUsageLog.cost_usd), 0.0))
        .where(LlmUsageLog.created_at >= week_ago)
    )
    ai_cost_7d = round(float(ai_7d_r.scalar() or 0), 6)

    # Total AI tokens / cost all time
    ai_total_r = await db.execute(
        select(
            func.coalesce(func.sum(LlmUsageLog.total_tokens), 0),
            func.coalesce(func.sum(LlmUsageLog.cost_usd), 0.0),
        )
    )
    ai_total_tokens, ai_total_cost = ai_total_r.one()

    return {
        "dau": dau,
        "dau_yesterday": dau_yd,
        "mau": mau,
        "total_users": total_users,
        "new_users_today": new_today,
        "new_users_7d": new_7d,
        "capsules_generated_today": caps_today,
        "capsules_generated_7d": caps_7d,
        "cards_reviewed_today": int(cards_today),
        "ai_cost_today_usd": ai_cost_today,
        "ai_cost_7d_usd": ai_cost_7d,
        "ai_total_tokens": int(ai_total_tokens),
        "ai_total_cost_usd": round(float(ai_total_cost), 4),
    }


# ── Activation funnel ─────────────────────────────────────────────────────────

@router.get("/funnel")
async def funnel(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    since = _days_ago(days)

    # Signups in period
    signups_r = await db.execute(
        select(func.count(User.id)).where(User.created_at >= since)
    )
    signups = signups_r.scalar() or 0

    # Users who created ≥1 topic
    topic_users_r = await db.execute(
        select(func.count(distinct(Topic.user_id)))
        .where(Topic.started_at >= since)
    )
    topic_users = topic_users_r.scalar() or 0

    # Users who generated ≥1 capsule
    capsule_users_r = await db.execute(
        select(func.count(distinct(Capsule.user_id)))
        .where(Capsule.created_at >= since)
    )
    capsule_users = capsule_users_r.scalar() or 0

    # Users who reviewed ≥1 card (have card session)
    card_users_r = await db.execute(
        select(func.count(distinct(CardSession.user_id)))
        .where(CardSession.session_date >= since.date())
    )
    card_users = card_users_r.scalar() or 0

    # Active last 7d (among those who signed up in period)
    active_7d_r = await db.execute(
        select(func.count(distinct(CardSession.user_id)))
        .where(CardSession.session_date >= _days_ago(7).date())
    )
    still_active_7d = active_7d_r.scalar() or 0

    def pct(n: int, base: int) -> float:
        return round(n / base * 100, 1) if base else 0.0

    return {
        "period_days": days,
        "signups": signups,
        "created_first_topic": topic_users,
        "generated_first_capsule": capsule_users,
        "reviewed_first_card": card_users,
        "still_active_7d": still_active_7d,
        "activation_rate_pct": pct(capsule_users, signups),
        "retention_7d_pct": pct(still_active_7d, capsule_users) if capsule_users else 0.0,
    }


# ── Retention cohorts ─────────────────────────────────────────────────────────

@router.get("/retention")
async def retention(
    weeks: int = Query(default=8, ge=2, le=52),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = []
    now_date = _today_utc()

    for w in range(weeks, 0, -1):
        week_start = now_date - timedelta(weeks=w)
        week_end = week_start + timedelta(days=6)

        # Cohort: users who signed up in this week
        cohort_r = await db.execute(
            select(User.id)
            .where(and_(
                func.date(User.created_at) >= week_start,
                func.date(User.created_at) <= week_end,
            ))
        )
        cohort_ids = [r[0] for r in cohort_r.all()]
        cohort_size = len(cohort_ids)
        if not cohort_ids:
            rows.append({"week": str(week_start), "cohort_size": 0})
            continue

        retained: dict[str, int] = {}
        for check_w in range(1, min(w + 1, 5)):  # check up to 4 weeks retention
            check_start = week_start + timedelta(weeks=check_w)
            check_end = check_start + timedelta(days=6)
            if check_start > now_date:
                break
            ret_r = await db.execute(
                select(func.count(distinct(CardSession.user_id)))
                .where(and_(
                    CardSession.user_id.in_(cohort_ids),
                    CardSession.session_date >= check_start,
                    CardSession.session_date <= check_end,
                ))
            )
            retained[f"w{check_w}"] = ret_r.scalar() or 0

        rows.append({
            "week": str(week_start),
            "cohort_size": cohort_size,
            **retained,
        })

    return rows


# ── AI usage ─────────────────────────────────────────────────────────────────

@router.get("/ai")
async def ai_usage(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    since = _days_ago(days)

    result = await db.execute(
        select(
            func.date(LlmUsageLog.created_at).label("date"),
            LlmUsageLog.call_type,
            func.count(LlmUsageLog.id).label("calls"),
            func.coalesce(func.sum(LlmUsageLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(LlmUsageLog.cost_usd), 0.0).label("total_cost_usd"),
            func.coalesce(func.avg(LlmUsageLog.latency_ms), 0).label("avg_latency_ms"),
        )
        .where(LlmUsageLog.created_at >= since)
        .group_by(func.date(LlmUsageLog.created_at), LlmUsageLog.call_type)
        .order_by(func.date(LlmUsageLog.created_at).desc(), LlmUsageLog.call_type)
    )

    rows = []
    for r in result.all():
        rows.append({
            "date": str(r.date),
            "call_type": r.call_type,
            "calls": r.calls,
            "total_tokens": int(r.total_tokens),
            "total_cost_usd": round(float(r.total_cost_usd), 6),
            "avg_latency_ms": int(r.avg_latency_ms or 0),
        })
    return rows


# ── Engagement ───────────────────────────────────────────────────────────────

@router.get("/engagement")
async def engagement(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    since_date = _days_ago(days).date()

    # Active users in period (have card sessions)
    active_r = await db.execute(
        select(func.count(distinct(CardSession.user_id)))
        .where(CardSession.session_date >= since_date)
    )
    active_users = active_r.scalar() or 1

    # Total cards reviewed
    total_cards_r = await db.execute(
        select(func.coalesce(func.sum(CardSession.cards_reviewed), 0))
        .where(CardSession.session_date >= since_date)
    )
    total_cards = int(total_cards_r.scalar() or 0)

    # Avg cards per active user
    avg_cards = round(total_cards / active_users, 1)

    # Streak stats
    streak_avg_r = await db.execute(
        select(func.avg(UserStreak.current_streak))
    )
    avg_streak = round(float(streak_avg_r.scalar() or 0), 1)

    streak_with_r = await db.execute(
        select(func.count(UserStreak.user_id)).where(UserStreak.current_streak > 0)
    )
    streak_total_r = await db.execute(select(func.count(UserStreak.user_id)))
    streak_with = streak_with_r.scalar() or 0
    streak_total = streak_total_r.scalar() or 1
    pct_with_streak = round(streak_with / max(streak_total, 1) * 100, 1)

    # Top topics by capsule count
    top_topics_r = await db.execute(
        select(Topic.name, func.count(Capsule.id).label("capsule_count"))
        .join(Capsule, Capsule.topic_id == Topic.id, isouter=True)
        .group_by(Topic.id, Topic.name)
        .order_by(func.count(Capsule.id).desc())
        .limit(5)
    )
    top_topics = [{"name": r.name, "capsule_count": r.capsule_count} for r in top_topics_r.all()]

    # Session frequency distribution
    sessions_per_user_r = await db.execute(
        select(
            CardSession.user_id,
            func.count(CardSession.id).label("sessions"),
        )
        .where(CardSession.session_date >= since_date)
        .group_by(CardSession.user_id)
    )
    session_counts = [r.sessions for r in sessions_per_user_r.all()]
    dist = {"1": 0, "2-5": 0, "6-15": 0, "16+": 0}
    for s in session_counts:
        if s == 1:
            dist["1"] += 1
        elif s <= 5:
            dist["2-5"] += 1
        elif s <= 15:
            dist["6-15"] += 1
        else:
            dist["16+"] += 1

    # Daily avg review quality (avg_rating from card_sessions)
    quality_r = await db.execute(
        select(func.avg(CardSession.avg_rating))
        .where(
            CardSession.session_date >= since_date,
            CardSession.avg_rating.isnot(None),
        )
    )
    avg_quality = round(float(quality_r.scalar() or 0), 2)

    return {
        "period_days": days,
        "active_users": active_users,
        "total_cards_reviewed": total_cards,
        "avg_cards_per_active_user": avg_cards,
        "avg_streak": avg_streak,
        "pct_users_with_streak": pct_with_streak,
        "avg_review_quality": avg_quality,
        "top_topics": top_topics,
        "session_frequency": dist,
    }


# ── Recent events ─────────────────────────────────────────────────────────────

@router.get("/events")
async def recent_events(
    limit: int = Query(default=50, ge=1, le=200),
    event_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    q = select(LearningEvent).order_by(LearningEvent.occurred_at.desc()).limit(limit)
    if event_type:
        q = q.where(LearningEvent.event_type == event_type)
    result = await db.execute(q)
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "event_type": e.event_type,
            "payload": e.payload,
            "occurred_at": e.occurred_at.isoformat(),
        }
        for e in events
    ]
