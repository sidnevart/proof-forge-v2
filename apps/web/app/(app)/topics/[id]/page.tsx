'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { getStoredUser } from '@/lib/auth'
import { topics, practice, type Topic, type TopicMaterial, type StudyProfile } from '@/lib/api'
import { OnboardingChat } from '@/components/OnboardingChat'
import { Skeleton } from '@/components/ui/Skeleton'
import { useT, useLocale, ruPlural } from '@/lib/i18n'

export default function TopicPage() {
  const { id: topicId } = useParams<{ id: string }>()
  const router = useRouter()
  const user = getStoredUser()
  const t = useT()
  const { locale } = useLocale()

  const [topic, setTopic] = useState<Topic | null>(null)
  const [materials, setMaterials] = useState<TopicMaterial[]>([])
  const [loadingTopic, setLoadingTopic] = useState(true)

  const [showMaterials, setShowMaterials] = useState(false)

  const [startingStudy, setStartingStudy] = useState(false)
  const [studyError, setStudyError] = useState('')

  const loadTopic = useCallback(async () => {
    if (!user) return
    try {
      const [tp, mats] = await Promise.all([
        topics.get(topicId),
        topics.getMaterials(topicId),
      ])
      setTopic(tp)
      setMaterials(mats)
    } catch {
      // topic not found
    } finally {
      setLoadingTopic(false)
    }
  }, [topicId, user?.user_id])

  useEffect(() => { loadTopic() }, [loadTopic])

  const handleStartStudy = useCallback(async (profile?: StudyProfile) => {
    if (!user || !topic) return
    setStartingStudy(true)
    setStudyError('')
    try {
      const result = await practice.startSession(user.user_id, topic.id, profile)
      router.push(`/study/${result.session.id}`)
    } catch (err: unknown) {
      setStudyError(err instanceof Error ? err.message : t('topic.startError'))
      setStartingStudy(false)
    }
  }, [user, topic, router, t])

  if (loadingTopic) {
    return (
      <div className="max-w-2xl mx-auto px-5 py-10 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (!topic) {
    return (
      <div className="max-w-2xl mx-auto px-5 py-16 text-center">
        <p className="text-mute">{t('topic.notFound')}</p>
        <Link href="/dashboard" className="text-accent text-sm mt-4 inline-block">{t('topic.back')}</Link>
      </div>
    )
  }

  const materialsLabel = (() => {
    const n = materials.length
    if (locale === 'ru') {
      const suffix = ruPlural(n, ['', 'а', 'ов'])
      return `${n} материал${suffix}`
    }
    return `${n} material${n !== 1 ? 's' : ''}`
  })()

  return (
    <div className="max-w-2xl mx-auto px-5 py-8">
      {/* Header */}
      <div className="mb-6">
        <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-xs text-mute hover:text-ink transition-colors mb-4 font-mono">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="15 18 9 12 15 6"/></svg>
          Dashboard
        </Link>
        <h1 className="font-display text-2xl sm:text-3xl font-bold text-ink">{topic.name}</h1>
      </div>

      {/* Study error */}
      {studyError && (
        <div className="mb-4 px-4 py-3 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger">
          {studyError}
        </div>
      )}

      {/* Adaptive interview — the purpose of this screen; starts immediately */}
      <div className="surface rounded-2xl p-5 mb-6">
        {startingStudy ? (
          <div className="flex items-center gap-2 py-4 justify-center">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            <span className="text-xs text-mute font-mono">{t('topic.study.launching')}</span>
          </div>
        ) : (
          <OnboardingChat
            userId={user!.user_id}
            topicId={topic.id}
            onConfirm={(profile) => handleStartStudy(profile)}
            onSkip={() => handleStartStudy()}
          />
        )}
      </div>

      {/* Materials — chosen during topic creation. Shown here read-only so the learner
          can see what the AI is working from; uploading lives only on the create screen. */}
      {materials.length > 0 && (
        <div className="mb-6">
          <button
            type="button"
            onClick={() => setShowMaterials((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-3 rounded-xl border border-line bg-card text-sm font-medium hover:border-accent/40 transition-colors"
          >
            <span className="flex items-center gap-2 text-mute">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              {materialsLabel}
            </span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className={`text-mute transition-transform ${showMaterials ? 'rotate-180' : ''}`}><polyline points="6 9 12 15 18 9"/></svg>
          </button>

          {showMaterials && (
            <div className="mt-3 space-y-2">
              {materials.map((m) => (
                <MaterialCard key={m.id} material={m} t={t} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function MaterialCard({ material, t }: { material: TopicMaterial; t: (k: string) => string }) {
  const [expanded, setExpanded] = useState(false)
  const preview = material.content_text.slice(0, 200).replace(/\n+/g, ' ').trim()
  const hasMore = material.content_text.length > 200

  return (
    <div className="surface rounded-xl p-4">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-card border border-line flex items-center justify-center shrink-0 mt-0.5">
          {material.type === 'link' ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-mute uppercase">{material.type}</span>
            {material.file_size && (
              <span className="text-xs text-mute">{formatSize(material.file_size)}</span>
            )}
          </div>
          <p className="text-sm font-medium text-ink truncate">{material.name}</p>
          {material.url && (
            <a href={material.url} target="_blank" rel="noopener noreferrer"
              className="text-xs text-accent hover:underline truncate block mt-0.5">
              {material.url}
            </a>
          )}
          {preview && (
            <div className="mt-2">
              <p className="text-xs text-mute leading-relaxed font-mono">
                {expanded ? material.content_text : preview}
                {!expanded && hasMore && '...'}
              </p>
              {hasMore && (
                <button
                  type="button"
                  onClick={() => setExpanded((v) => !v)}
                  className="text-xs text-accent hover:text-accentdk mt-1 font-mono"
                >
                  {expanded ? t('topic.collapse') : `${t('topic.showAll')} (${formatChars(material.content_text.length)})`}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

function formatChars(n: number) {
  if (n >= 1000) return `${(n / 1000).toFixed(0)}K chars`
  return `${n} chars`
}
