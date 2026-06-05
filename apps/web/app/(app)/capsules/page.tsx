'use client'

import { useEffect, useState, useMemo } from 'react'
import Link from 'next/link'
import { capsules, topics, type Capsule, type Topic } from '@/lib/api'
import { getStoredUser } from '@/lib/auth'
import { SkeletonText } from '@/components/ui/Skeleton'
import { useT } from '@/lib/i18n'

export default function CapsulesPage() {
  const user = getStoredUser()
  const [allCapsules, setAllCapsules] = useState<Capsule[]>([])
  const [allTopics, setAllTopics] = useState<Topic[]>([])
  const [search, setSearch] = useState('')
  const [topicFilter, setTopicFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const t = useT()

  useEffect(() => {
    if (!user) return
    setLoading(true)
    Promise.all([
      capsules.list(user.user_id, topicFilter || undefined),
      topics.list(user.user_id),
    ]).then(([caps, tops]) => {
      setAllCapsules(caps)
      setAllTopics(tops)
    }).finally(() => setLoading(false))
  }, [user?.user_id, topicFilter])

  const filtered = useMemo(() => {
    let result = allCapsules
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter((c) => c.summary.toLowerCase().includes(q))
    }
    return result
  }, [allCapsules, search])

  return (
    <div className="max-w-3xl mx-auto px-5 py-8">
      <h1 className="font-display text-2xl font-bold text-ink mb-6">{t('capsules.title')}</h1>

      {/* Search + filter */}
      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('capsules.search')}
          className="flex-1 px-4 py-2.5 rounded-xl border border-line bg-card text-ink placeholder:text-mute/50 text-sm focus:outline-none focus:border-accent/60 transition-colors"
        />
        <select
          value={topicFilter}
          onChange={(e) => setTopicFilter(e.target.value)}
          className="px-4 py-2.5 rounded-xl border border-line bg-card text-ink text-sm focus:outline-none focus:border-accent/60 transition-colors"
        >
          <option value="">{t('capsules.topicFilter')}</option>
          {allTopics.map((topic) => (
            <option key={topic.id} value={topic.id}>{topic.name}</option>
          ))}
        </select>
      </div>

      {/* Capsules list */}
      {loading ? (
        <SkeletonText lines={6} />
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <div className="w-12 h-12 rounded-2xl bg-accentsoft border border-accent/20 flex items-center justify-center mx-auto mb-3">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="3"/>
              <line x1="9" y1="9" x2="15" y2="9"/>
              <line x1="9" y1="13" x2="15" y2="13"/>
            </svg>
          </div>
          <p className="text-mute text-sm">{t('capsules.empty')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((capsule) => (
            <Link
              key={capsule.id}
              href={`/capsule/${capsule.id}`}
              className="surface surface-hover rounded-xl p-4 flex items-start gap-3 block"
            >
              <div className="w-8 h-8 rounded-lg bg-accentsoft border border-accent/20 flex items-center justify-center shrink-0 mt-0.5">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="3"/>
                  <line x1="9" y1="9" x2="15" y2="9"/>
                  <line x1="9" y1="13" x2="15" y2="13"/>
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-ink line-clamp-2">{capsule.summary}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[10px] font-mono text-mute">
                    {new Date(capsule.created_at).toLocaleDateString()}
                  </span>
                  {capsule.review_questions.length > 0 && (
                    <span className="text-[10px] font-mono text-accent">
                      {capsule.review_questions.length} questions
                    </span>
                  )}
                </div>
              </div>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-mute shrink-0 mt-1">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
