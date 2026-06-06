'use client'

import { useEffect, useState, useCallback } from 'react'
import { getStoredUser } from '@/lib/auth'
import { cards, topics, type DueCard, type Topic } from '@/lib/api'
import { FlipCard } from '@/components/FlipCard'
import { StreakCounter } from '@/components/StreakCounter'
import { Skeleton } from '@/components/ui/Skeleton'
import Link from 'next/link'
import { track } from '@/lib/analytics'
import { useT, useLocale, ruPlural } from '@/lib/i18n'

type SessionStats = { reviewed: number; again: number; hard: number; easy: number }

export default function CardsPage() {
  const user = getStoredUser()
  const [queue, setQueue] = useState<DueCard[]>([])
  const [current, setCurrent] = useState(0)
  const [loading, setLoading] = useState(true)
  const [rating, setRating] = useState(false)
  const [done, setDone] = useState(false)
  const [streak, setStreak] = useState(0)
  const [session, setSession] = useState<SessionStats>({ reviewed: 0, again: 0, hard: 0, easy: 0 })
  const [topicList, setTopicList] = useState<Topic[]>([])
  const [topicFilter, setTopicFilter] = useState<string>('') // '' = all topics
  const t = useT()
  const { locale } = useLocale()

  // Load the user's topics once for the filter chips.
  useEffect(() => {
    if (!user) return
    topics.list(user.user_id).then(setTopicList).catch(() => {})
  }, [user?.user_id])

  const loadCards = useCallback(async () => {
    if (!user) return
    setLoading(true)
    try {
      const [due, stats] = await Promise.all([
        cards.due(user.user_id, 30, topicFilter || undefined),
        cards.stats(user.user_id, topicFilter || undefined),
      ])
      setQueue(due)
      setStreak(stats.streak)
      setCurrent(0)
      setSession({ reviewed: 0, again: 0, hard: 0, easy: 0 })
      if (due.length === 0) {
        setDone(true)
      } else {
        setDone(false)
        track({ name: 'card_session_start', props: { due_count: due.length, topic: topicFilter || 'all' } })
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [user?.user_id, topicFilter])

  useEffect(() => { loadCards() }, [loadCards])

  const handleRate = async (ratingVal: 1 | 2 | 3 | 4) => {
    if (!user || rating) return
    const card = queue[current]
    setRating(true)
    try {
      await cards.attempt(card.card_id, user.user_id, ratingVal, '', card.source)
      setSession((s) => {
        const next = { ...s, reviewed: s.reviewed + 1 }
        if (ratingVal === 1) next.again += 1
        else if (ratingVal === 2) next.hard += 1
        else next.easy += 1
        return next
      })
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
        {[0,1,2].map(i => <Skeleton key={i} className="h-12 flex-1" />)}
      </div>
    </div>
  )

  if (done) {
    if (session.reviewed > 0) {
      const pctEasy = Math.round((session.easy / session.reviewed) * 100)
      track({ name: 'card_session_end', props: { reviewed: session.reviewed, easy_pct: pctEasy, streak } })
    }
    return (
      <div className="max-w-md mx-auto px-5 pt-8">
        {topicList.length > 1 && (
          <TopicChips topics={topicList} value={topicFilter} onChange={setTopicFilter} t={t} />
        )}
        <DoneScreen session={session} streak={streak} locale={locale} t={t} onRestart={() => { setDone(false); setCurrent(0); loadCards() }} />
      </div>
    )
  }

  const card = queue[current]
  if (!card) return null

  const progress = (current + 1) / queue.length

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

      {/* Topic filter */}
      {topicList.length > 1 && (
        <TopicChips topics={topicList} value={topicFilter} onChange={setTopicFilter} t={t} />
      )}

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
        cardType={card.card_type}
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
  const pctEasy = session.reviewed > 0
    ? Math.round((session.easy / session.reviewed) * 100)
    : 0

  const reviewedWord = locale === 'ru'
    ? ruPlural(session.reviewed, ['карточку', 'карточки', 'карточек'])
    : `card${session.reviewed !== 1 ? 's' : ''}`

  return (
    <div className="max-w-md mx-auto px-5 py-12 text-center">
      <div className="text-5xl mb-6">
        {pctEasy >= 80 ? '🔥' : pctEasy >= 50 ? '💪' : '📚'}
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
          <div className="grid grid-cols-3 gap-3">
            <Stat label={t('cards.done.again')} value={session.again} color="text-danger" />
            <Stat label={t('cards.done.hard')} value={session.hard} color="text-warn" />
            <Stat label={t('cards.done.easy')} value={session.easy} color="text-info" />
          </div>
          <div className="mt-4 pt-4 border-t border-line flex items-center justify-between">
            <span className="text-sm text-mute">{t('cards.done.accuracy')}</span>
            <span className={`text-lg font-mono font-bold ${pctEasy >= 70 ? 'text-accent' : 'text-warn'}`}>
              {pctEasy}%
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

function TopicChips({ topics, value, onChange, t }: {
  topics: Topic[]; value: string; onChange: (v: string) => void; t: (k: string) => string
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 mb-4 -mx-1 px-1">
      <button
        onClick={() => onChange('')}
        className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${
          value === ''
            ? 'bg-accent text-[#06140d] border-accent'
            : 'bg-card text-mute border-line hover:text-ink hover:border-accent/40'
        }`}
      >
        {t('cards.allTopics')}
      </button>
      {topics.map((topic) => (
        <button
          key={topic.id}
          onClick={() => onChange(topic.id)}
          className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors border max-w-[12rem] truncate ${
            value === topic.id
              ? 'bg-accent text-[#06140d] border-accent'
              : 'bg-card text-mute border-line hover:text-ink hover:border-accent/40'
          }`}
        >
          {topic.name}
        </button>
      ))}
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
