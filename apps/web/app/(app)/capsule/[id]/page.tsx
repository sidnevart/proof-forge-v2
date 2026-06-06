'use client'

import { useEffect, useState, useMemo, useRef, useCallback } from 'react'
import { use } from 'react'
import { capsules, topics, type Capsule, type CapsuleFeedback } from '@/lib/api'
import { useSSEStream } from '@/hooks/useSSEStream'
import { getStoredUser } from '@/lib/auth'
import { track } from '@/lib/analytics'
import { Skeleton, SkeletonText } from '@/components/ui/Skeleton'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { extractHeadings, slugify } from '@/app/(app)/_components/toc'
import Link from 'next/link'
import { useT, useLocale } from '@/lib/i18n'

export default function CapsulePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const user = getStoredUser()
  const [capsule, setCapsule] = useState<Capsule | null>(null)
  const [feedback, setFeedback] = useState<CapsuleFeedback | null | undefined>(undefined)
  const [loadingFeedback, setLoadingFeedback] = useState(false)
  const [loading, setLoading] = useState(true)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [regenEventsUrl, setRegenEventsUrl] = useState<string | null>(null)
  const pendingRegenId = useRef<string | null>(null)
  const [activeHeading, setActiveHeading] = useState('')
  const [showFeedback, setShowFeedback] = useState(false)
  const [tocOpen, setTocOpen] = useState(false)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const titleInputRef = useRef<HTMLInputElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const t = useT()
  const { locale } = useLocale()

  useSSEStream(regenEventsUrl, (event) => {
    if (event.type === 'complete') {
      setRegenEventsUrl(null)
      capsules.get(id).then((c) => {
        setCapsule(c)
        setIsRegenerating(false)
      }).catch(() => setIsRegenerating(false))
    } else if (event.type === 'error') {
      setRegenEventsUrl(null)
      setIsRegenerating(false)
    }
  })

  const handleRegenerate = useCallback(async () => {
    if (!user || !capsule || isRegenerating) return
    setIsRegenerating(true)
    try {
      const result = await topics.generateCapsule(capsule.topic_id, user.user_id, undefined, capsule.id)
      pendingRegenId.current = result.capsule_id
      setRegenEventsUrl(topics.capsuleEventsUrl(capsule.topic_id, result.capsule_id))
    } catch {
      setIsRegenerating(false)
    }
  }, [user, capsule, isRegenerating])

  useEffect(() => {
    Promise.all([
      capsules.get(id),
      capsules.feedback(id),
    ]).then(([c, f]) => {
      setCapsule(c)
      setFeedback(f)
      track({ name: 'capsule_viewed', props: { capsule_id: id } })
    }).catch(console.error).finally(() => setLoading(false))
  }, [id])

  // Track active heading on scroll
  useEffect(() => {
    if (!contentRef.current) return
    const headings = contentRef.current.querySelectorAll('h2[id]')
    if (!headings.length) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]) {
          setActiveHeading(visible[0].target.id)
        }
      },
      { rootMargin: '-80px 0px -60% 0px' }
    )
    headings.forEach((h) => observer.observe(h))
    return () => observer.disconnect()
  }, [capsule?.content_md])

  const headings = useMemo(() => {
    if (!capsule) return []
    const h = extractHeadings(capsule.content_md)
    if (capsule.review_questions.length > 0) {
      h.push({ id: 'review-questions', text: t('capsule.reviewQuestions'), level: 2 })
    }
    return h
  }, [capsule, t])

  const requestFeedback = async () => {
    if (!user) return
    setLoadingFeedback(true)
    track({ name: 'ai_feedback_clicked', props: { capsule_id: id } })
    try {
      const f = await capsules.requestFeedback(id)
      setFeedback(f)
      setShowFeedback(true)
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingFeedback(false)
    }
  }

  const scrollTo = (headingId: string) => {
    const el = document.getElementById(headingId)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setActiveHeading(headingId)
    }
  }

  const commitTitleRename = async () => {
    if (!capsule) { setEditingTitle(false); return }
    const next = titleDraft.trim()
    setEditingTitle(false)
    if (!next || next === (capsule.title || capsule.summary)) return
    try {
      const updated = await capsules.update(capsule.id, next)
      setCapsule((prev) => (prev ? { ...prev, title: updated.title } : prev))
    } catch {
      /* keep old title on failure */
    }
  }

  if (loading) return (
    <div className="max-w-2xl mx-auto px-5 py-8 space-y-4">
      <Skeleton className="h-8 w-48" />
      <SkeletonText lines={5} />
    </div>
  )

  if (!capsule) return (
    <div className="max-w-xl mx-auto px-5 py-20 text-center">
      <p className="text-mute">{t('capsule.notFound')}</p>
      <Link href="/dashboard" className="mt-4 inline-block text-accent hover:text-accentdk">{t('capsule.back')}</Link>
    </div>
  )

  const displayTitle = capsule.title || capsule.summary
  const questionsCount = capsule.review_questions.length
  const questionsLabel = locale === 'ru'
    ? `${questionsCount} ${questionsCount % 10 === 1 && questionsCount % 100 !== 11 ? 'вопрос' : questionsCount % 10 >= 2 && questionsCount % 10 <= 4 && (questionsCount % 100 < 10 || questionsCount % 100 >= 20) ? 'вопроса' : 'вопросов'}`
    : `${questionsCount} question${questionsCount !== 1 ? 's' : ''}`

  return (
    <div className="flex h-[calc(100vh-1px)] max-h-screen">
      {/* TOC Sidebar — compact: top-level sections by default, expandable to subsections */}
      <aside className="hidden lg:flex flex-col w-52 shrink-0 border-r border-line bg-sand/20 overflow-y-auto">
        <div className="px-4 py-6">
          <Link href="/dashboard" className="flex items-center gap-1.5 text-xs text-mute hover:text-ink transition-colors mb-6 font-mono">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            Dashboard
          </Link>
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-mono text-mute uppercase tracking-wider">{t('capsule.toc')}</span>
            {headings.some((h) => h.level === 3) && (
              <button
                onClick={() => setTocOpen((v) => !v)}
                className="text-[10px] font-mono text-mute hover:text-accent transition-colors"
              >
                {tocOpen ? t('capsule.toc.collapse') : t('capsule.toc.expand')}
              </button>
            )}
          </div>
          <nav className="space-y-0.5 max-h-[calc(100vh-9rem)] overflow-y-auto">
            {(tocOpen ? headings : headings.filter((h) => h.level === 2)).map((h) => (
              <button
                key={h.id}
                onClick={() => scrollTo(h.id)}
                className={`block w-full text-left px-2 py-1 rounded-md text-xs transition-colors truncate ${
                  h.level === 3 ? 'pl-4 text-mute/80' : ''
                } ${
                  activeHeading === h.id
                    ? 'bg-accentsoft text-accent font-medium'
                    : 'text-mute hover:text-ink hover:bg-card'
                }`}
              >
                {h.text}
              </button>
            ))}
          </nav>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Header */}
        <div className="shrink-0 border-b border-line px-5 py-4 bg-paper/90 backdrop-blur-md">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 group">
                <div className="text-[10px] font-mono text-accent uppercase tracking-wider mb-1">{t('capsule.tag')}</div>
                {editingTitle ? (
                  <input
                    ref={titleInputRef}
                    value={titleDraft}
                    onChange={(e) => setTitleDraft(e.target.value)}
                    onBlur={commitTitleRename}
                    onKeyDown={(e) => { if (e.key === 'Enter') commitTitleRename(); if (e.key === 'Escape') setEditingTitle(false) }}
                    className="font-display text-xl sm:text-2xl font-bold text-ink leading-tight bg-card border border-accent/60 rounded-lg px-2 py-0.5 focus:outline-none w-full"
                    autoFocus
                  />
                ) : (
                  <div className="flex items-center gap-2">
                    <h1 className="font-display text-xl sm:text-2xl font-bold text-ink leading-tight truncate">{displayTitle}</h1>
                    <button
                      onClick={() => { setTitleDraft(displayTitle); setEditingTitle(true); setTimeout(() => titleInputRef.current?.select(), 0) }}
                      className="shrink-0 text-mute opacity-0 group-hover:opacity-100 transition-opacity hover:text-accent"
                      aria-label={t('capsule.rename')}
                      title={t('capsule.rename')}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                      </svg>
                    </button>
                  </div>
                )}
                <p className="text-xs text-mute mt-1 font-mono">
                  {new Date(capsule.created_at).toLocaleDateString(locale === 'ru' ? 'ru' : 'en-US', { day: 'numeric', month: 'long', year: 'numeric' })}
                  {' · '}{questionsLabel}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Link
                  href={`/learn/${capsule.topic_id}`}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-accentsoft border border-accent/30 text-accent text-xs font-medium hover:bg-accent hover:text-[#06140d] transition-all"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.2" fill="currentColor"/>
                  </svg>
                  {t('capsule.mentor')}
                </Link>
                <button
                  onClick={handleRegenerate}
                  disabled={isRegenerating}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-accentsoft border border-accent/30 text-accent text-xs font-medium hover:bg-accent hover:text-[#06140d] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isRegenerating ? (
                    <div className="w-3 h-3 rounded-full border border-current border-t-transparent animate-spin" />
                  ) : (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/>
                    </svg>
                  )}
                  {isRegenerating ? '' : t('capsule.regenerate')}
                </button>
                <button
                  onClick={() => setShowFeedback((v) => !v)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border text-xs font-medium transition-all ${
                    showFeedback
                      ? 'bg-accent text-[#06140d] border-accent'
                      : 'bg-accentsoft border-accent/30 text-accent hover:bg-accent hover:text-[#06140d]'
                  }`}
                >
                  🤖
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-5 py-6 pb-24">
            <div ref={contentRef} className="prose-grasp">
              <MarkdownRenderer
                components={{
                  h1: ({ children }) => (
                    <h1 className="font-display text-2xl font-bold text-ink mt-2 mb-4">{children}</h1>
                  ),
                  h2: ({ children }) => {
                    const text = typeof children === 'string' ? children : String(children ?? '')
                    return <h2 id={slugify(text.trim())} className="font-display text-lg font-bold text-ink mt-8 mb-3 pb-2 border-b border-line/60 scroll-mt-24">{children}</h2>
                  },
                  h3: ({ children }) => {
                    const text = typeof children === 'string' ? children : String(children ?? '')
                    return <h3 id={slugify(text.trim())} className="font-semibold text-ink mt-6 mb-2 scroll-mt-24">{children}</h3>
                  },
                  p: ({ children }) => <p className="text-ink/90 leading-relaxed mb-3">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-3 text-ink/90">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-3 text-ink/90">{children}</ol>,
                  hr: () => <hr className="my-6 border-line/40" />,
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-accent pl-4 my-3 text-mute italic">{children}</blockquote>
                  ),
                }}
              >
                {capsule.content_md}
              </MarkdownRenderer>
            </div>

            {/* Review questions inline */}
            {capsule.review_questions.length > 0 && (
              <div id="review-questions" className="mt-10 pt-6 border-t border-line scroll-mt-20">
                <h2 className="font-display text-lg font-bold text-ink mb-4">{t('capsule.reviewQuestions')}</h2>
                <div className="space-y-2">
                  {capsule.review_questions.map((q, i) => (
                    <details key={q.id} className="surface surface-hover rounded-xl overflow-hidden group">
                      <summary className="flex items-start gap-3 p-4 cursor-pointer list-none">
                        <span className="w-6 h-6 rounded-lg bg-sand text-mute flex items-center justify-center text-xs font-mono shrink-0 mt-0.5">
                          {i + 1}
                        </span>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-ink">{q.question}</p>
                          <p className="text-xs text-mute mt-1 font-mono">
                            {t('capsule.difficultyLabel')}: {'◆'.repeat(q.difficulty)}{'◇'.repeat(3 - q.difficulty)}
                          </p>
                        </div>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-mute group-open:rotate-90 transition-transform shrink-0 mt-1">
                          <polyline points="9 18 15 12 9 6"/>
                        </svg>
                      </summary>
                      <div className="px-4 pb-4 pt-0">
                        <div className="bg-accentsoft border border-accent/20 rounded-lg p-3">
                          <p className="text-xs font-mono text-accent mb-1">{t('capsule.answerLabel')}</p>
                          <p className="text-sm text-ink">{q.correct_answer}</p>
                        </div>
                      </div>
                    </details>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Feedback sidebar */}
      {showFeedback && (
        <div className="hidden xl:flex flex-col w-80 shrink-0 border-l border-line bg-sand/20 overflow-y-auto">
          <div className="px-5 py-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-[10px] font-mono text-mute uppercase tracking-wider">{t('capsule.feedback.title')}</div>
              <button onClick={() => setShowFeedback(false)} className="text-mute hover:text-ink">✕</button>
            </div>
            {feedback === undefined || loadingFeedback ? (
              <SkeletonText lines={6} />
            ) : feedback ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-mute">
                  <span>{feedback.model_version}</span>
                  <span>·</span>
                  <span>{new Date(feedback.generated_at).toLocaleDateString(locale === 'ru' ? 'ru' : 'en-US')}</span>
                </div>
                <div className="surface rounded-2xl p-4">
                  <MarkdownRenderer
                    components={{
                      h2: ({ children }) => <h2 className="font-semibold text-ink mt-3 mb-1 text-sm">{children}</h2>,
                      h3: ({ children }) => <h3 className="font-medium text-ink mt-2 mb-1 text-xs">{children}</h3>,
                      p: ({ children }) => <p className="text-ink/90 leading-relaxed mb-2 text-xs">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2 text-xs text-ink/90">{children}</ul>,
                    }}
                  >
                    {feedback.suggestions_md}
                  </MarkdownRenderer>
                </div>
                <button
                  onClick={requestFeedback}
                  disabled={loadingFeedback}
                  className="text-xs text-mute hover:text-accent transition-colors font-mono"
                >
                  {t('capsule.feedback.refresh')}
                </button>
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="text-3xl mb-3">🤖</div>
                <p className="text-xs text-mute mb-4">{t('capsule.feedback.empty')}</p>
                <button
                  onClick={requestFeedback}
                  disabled={loadingFeedback}
                  className="px-4 py-2 rounded-xl bg-accent text-[#06140d] text-xs font-semibold hover:bg-accentdk transition-colors disabled:opacity-60"
                >
                  {loadingFeedback ? t('capsule.feedback.analyzing') : t('capsule.feedback.get')}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
