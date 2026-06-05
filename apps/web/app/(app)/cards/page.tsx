'use client'

import { useEffect, useState, useCallback } from 'react'
import { getStoredUser } from '@/lib/auth'
import { cards, type DueCard } from '@/lib/api'
import { FlipCard } from '@/components/FlipCard'
import { StreakCounter } from '@/components/StreakCounter'
import { Skeleton } from '@/components/ui/Skeleton'
import Link from 'next/link'
import { track } from '@/lib/analytics'
import { useT, useLocale, ruPlural } from '@/lib/i18n'

type SessionStats = { reviewed: number; again: number; hard: number; good: number; easy: number }

export default function CardsPage() {
  const user = getStoredUser()
  const [queue, setQueue] = useState<DueCard[]>([])
  const [current, setCurrent] = useState(0)
  const [loading, setLoading] = useState(true)
  const [rating, setRating] = useState(false)
  const [done, setDone] = useState(false)
  const [streak, setStreak] = useState(0)
  const [session, setSession] = useState<SessionStats>({ reviewed: 0, again: 0, hard: 0, good: 0, easy: 0 })
  const t = useT()
  const { locale } = useLocale()

  const loadCards = useCallback(async () => {
    if (!user) return
    setLoading(true)
    try {
      const [due, stats] = await Promise.all([
        cards.due(user.user_id, 30),
        cards.stats(user.user_id),
      ])
      setQueue(due)
      setStreak(stats.streak)
      if (due.length === 0) {
        setDone(true)
      } else {
        track({ name: 'card_session_start', props: { due_count: due.length } })
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [user?.user_id])

  useEffect(() => { loadCards() }, [loadCards])

  const handleRate = async (ratingVal: 1 | 2 | 3 | 4) => {
    if (!user || rating) return
    const card = queue[current]
    setRating(true)
    try {
      await cards.attempt(card.card_id, user.user_id, ratingVal)
      const key = ratingVal === 1 ? 'again' : ratingVal === 2 ? 'hard' : ratingVal === 3 ? 'good' : 'easy'
      setSession((s) => ({ ...s, reviewed: s.reviewed + 1, [key]: s[key] + 1 }))
      track({ name: 'card_rated', props: { rating: ratingVal, topic: card.topic_name } })

      if (current + 1 >= queue.length) {
        setDone(true)
      } else {
        setCurrent((c) => c + 1)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setRating(false)
    }
  }

  if (loading) return (
    <div className="max-w-lg mx-auto px-5 py-12 space-y-4">
      <Skeleton className="h-6 w-32" />
      <Skeleton className="h-64 w-full" />
      <div className="flex gap-2">
        {[0,1,2,3].map(i => <Skeleton key={i} className="h-12 flex-1" />)}
      </div>
    </div>
  )

  if (done) {
    if (session.reviewed > 0) {
      const pctGood = Math.round(((session.good + session.easy) / session.reviewed) * 100)
      track({ name: 'card_session_end', props: { reviewed: session.reviewed, good_pct: pctGood, streak } })
    }
    return <DoneScreen session={session} streak={streak} locale={locale} t={t} onRestart={() => { setDone(false); setCurrent(0); loadCards() }} />
  }

  const card = queue[current]
  if (!card) return null

  const progress = current / queue.length

  return (
    <div className="max-w-lg mx-auto px-5 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink">{t('cards.title')}</h1>
          <p className="text-sm text-mute font-mono mt-0.5">{current + 1} / {queue.length}</p>
        </div>
        <StreakCounter streak={streak} size="sm" />
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-sand rounded-full mb-8 overflow-hidden">
        <div
          className="h-full bg-accent rounded-full prog-fill"
          style={{ width: `${progress * 100}%` }}
        />
      </div>

      {/* Card */}
      <FlipCard
        question={card.question}
        answer={card.correct_answer}
        difficulty={card.difficulty}
        topic={card.topic_name}
        onRate={handleRate}
        isLoading={rating}
      />

      {/* Skip link */}
      <div className="mt-8 text-center">
        <Link href="/dashboard" className="text-xs text-mute hover:text-ink transition-colors font-mono">
          {t('cards.back')}
        </Link>
      </div>
    </div>
  )
}

function DoneScreen({ session, streak, locale, t, onRestart }: {
  session: SessionStats; streak: number; locale: string; t: (k: string) => string; onRestart: () => void
}) {
  const pctGood = session.reviewed > 0
    ? Math.round(((session.good + session.easy) / session.reviewed) * 100)
    : 0

  const reviewedWord = locale === 'ru'
    ? ruPlural(session.reviewed, ['карточку', 'карточки', 'карточек'])
    : `card${session.reviewed !== 1 ? 's' : ''}`

  return (
    <div className="max-w-md mx-auto px-5 py-12 text-center">
      <div className="text-5xl mb-6">
        {pctGood >= 80 ? '🔥' : pctGood >= 50 ? '💪' : '📚'}
      </div>
      <h1 className="font-display text-3xl font-bold text-ink mb-2">
        {session.reviewed === 0 ? t('cards.done.allReviewed') : t('cards.done.sessionComplete')}
      </h1>
      <p className="text-mute mb-8">
        {session.reviewed === 0
          ? t('cards.done.empty')
          : `${t('cards.done.reviewedPrefix')} ${session.reviewed} ${reviewedWord}`}
      </p>

      {session.reviewed > 0 && (
        <div className="surface rounded-2xl p-6 mb-8 text-left">
          <div className="text-xs font-mono text-mute mb-4">{t('cards.done.results')}</div>
          <div className="grid grid-cols-2 gap-3">
            <Stat label={t('cards.done.again')} value={session.again} color="text-danger" />
            <Stat label={t('cards.done.hard')} value={session.hard} color="text-warn" />
            <Stat label={t('cards.done.good')} value={session.good} color="text-accent" />
            <Stat label={t('cards.done.easy')} value={session.easy} color="text-info" />
          </div>
          <div className="mt-4 pt-4 border-t border-line flex items-center justify-between">
            <span className="text-sm text-mute">{t('cards.done.accuracy')}</span>
            <span className={`text-lg font-mono font-bold ${pctGood >= 70 ? 'text-accent' : 'text-warn'}`}>
              {pctGood}%
            </span>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3">
        <Link href="/dashboard" className="w-full py-3.5 rounded-xl bg-accent text-[#06140d] font-semibold hover:bg-accentdk transition-colors text-center">
          {t('cards.done.home')}
        </Link>
        <Link href="/progress" className="w-full py-3.5 rounded-xl surface text-ink font-medium hover:border-accent/40 transition-colors text-center">
          {t('cards.done.progress')}
        </Link>
      </div>
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-mute">{label}</span>
      <span className={`text-lg font-mono font-bold ${color}`}>{value}</span>
    </div>
  )
}
