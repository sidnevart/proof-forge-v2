'use client'

import { useEffect, useState, useMemo, useRef } from 'react'
import { use } from 'react'
import { capsules, type Capsule, type CapsuleFeedback } from '@/lib/api'
import { getStoredUser } from '@/lib/auth'
import { track } from '@/lib/analytics'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Skeleton, SkeletonText } from '@/components/ui/Skeleton'
import Link from 'next/link'

function extractHeadings(md: string): { id: string; text: string; level: number }[] {
  const lines = md.split('\n')
  const headings: { id: string; text: string; level: number }[] = []
  for (const line of lines) {
    const match = line.match(/^(#{2,3})\s+(.+)$/)
    if (match) {
      const text = match[2].trim()
      const id = text.toLowerCase().replace(/[^a-z0-9а-яё]+/g, '-').replace(/^-|-$/g, '')
      headings.push({ id: `${id}-${headings.length}`, text, level: match[1].length })
    }
  }
  return headings
}

function slugify(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9а-яё]+/g, '-').replace(/^-|-$/g, '')
}

export default function CapsulePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const user = getStoredUser()
  const [capsule, setCapsule] = useState<Capsule | null>(null)
  const [feedback, setFeedback] = useState<CapsuleFeedback | null | undefined>(undefined)
  const [loadingFeedback, setLoadingFeedback] = useState(false)
  const [loading, setLoading] = useState(true)
  const [activeHeading, setActiveHeading] = useState('')
  const [showFeedback, setShowFeedback] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

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
      h.push({ id: 'review-questions', text: 'Вопросы для повторения', level: 2 })
    }
    return h
  }, [capsule])

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

  if (loading) return (
    <div className="max-w-2xl mx-auto px-5 py-8 space-y-4">
      <Skeleton className="h-8 w-48" />
      <SkeletonText lines={5} />
    </div>
  )

  if (!capsule) return (
    <div className="max-w-xl mx-auto px-5 py-20 text-center">
      <p className="text-mute">Капсула не найдена</p>
      <Link href="/dashboard" className="mt-4 inline-block text-accent hover:text-accentdk">← Назад</Link>
    </div>
  )

  const headingCounter = new Map<string, number>()
  const getHeadingId = (text: string) => {
    const base = slugify(text)
    const count = (headingCounter.get(base) ?? 0) + 1
    headingCounter.set(base, count)
    return count > 1 ? `${base}-${count}` : base
  }
  headingCounter.clear()

  return (
    <div className="flex h-[calc(100vh-1px)] max-h-screen">
      {/* TOC Sidebar */}
      <aside className="hidden lg:flex flex-col w-64 shrink-0 border-r border-line bg-sand/20 overflow-y-auto">
        <div className="px-5 py-6">
          <Link href="/dashboard" className="flex items-center gap-1.5 text-xs text-mute hover:text-ink transition-colors mb-6 font-mono">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            Dashboard
          </Link>
          <div className="text-[10px] font-mono text-mute uppercase tracking-wider mb-3">Оглавление</div>
          <nav className="space-y-0.5">
            {headings.map((h) => (
              <button
                key={h.id}
                onClick={() => scrollTo(h.id)}
                className={`block w-full text-left px-2 py-1 rounded-md text-xs transition-colors ${
                  h.level === 3 ? 'pl-4' : ''
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
              <div>
                <div className="text-[10px] font-mono text-accent uppercase tracking-wider mb-1">Капсула знаний</div>
                <h1 className="font-display text-xl sm:text-2xl font-bold text-ink leading-tight">{capsule.summary}</h1>
                <p className="text-xs text-mute mt-1 font-mono">
                  {new Date(capsule.created_at).toLocaleDateString('ru', { day: 'numeric', month: 'long', year: 'numeric' })}
                  {' · '}{capsule.review_questions.length} вопросов
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
                  Ментор
                </Link>
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
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ children }) => (
                    <h1 className="font-display text-2xl font-bold text-ink mt-2 mb-4">{children}</h1>
                  ),
                  h2: ({ children }) => {
                    const text = String(children).trim()
                    const id = getHeadingId(text)
                    return <h2 id={id} className="font-display text-lg font-bold text-ink mt-8 mb-3 scroll-mt-20">{children}</h2>
                  },
                  h3: ({ children }) => (
                    <h3 className="font-semibold text-ink mt-5 mb-2 text-sm">{children}</h3>
                  ),
                  p: ({ children }) => <p className="text-ink/90 leading-relaxed mb-3 text-sm">{children}</p>,
                  code: ({ children, className }) =>
                    className ? (
                      <code className="code-surface block p-4 rounded-xl font-mono text-xs my-3 overflow-x-auto whitespace-pre">{children}</code>
                    ) : (
                      <code className="font-mono text-accent bg-accentsoft px-1 py-0.5 rounded text-xs">{children}</code>
                    ),
                  ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-3 text-ink/90 text-sm">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-3 text-ink/90 text-sm">{children}</ol>,
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-accent pl-4 my-3 text-mute italic text-sm">{children}</blockquote>
                  ),
                }}
              >
                {capsule.content_md}
              </ReactMarkdown>
            </div>

            {/* Review questions inline */}
            {capsule.review_questions.length > 0 && (
              <div id="review-questions" className="mt-10 pt-6 border-t border-line scroll-mt-20">
                <h2 className="font-display text-lg font-bold text-ink mb-4">Вопросы для повторения</h2>
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
                            сложность: {'◆'.repeat(q.difficulty)}{'◇'.repeat(3 - q.difficulty)}
                          </p>
                        </div>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-mute group-open:rotate-90 transition-transform shrink-0 mt-1">
                          <polyline points="9 18 15 12 9 6"/>
                        </svg>
                      </summary>
                      <div className="px-4 pb-4 pt-0">
                        <div className="bg-accentsoft border border-accent/20 rounded-lg p-3">
                          <p className="text-xs font-mono text-accent mb-1">ответ</p>
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
              <div className="text-[10px] font-mono text-mute uppercase tracking-wider">AI-фидбэк</div>
              <button onClick={() => setShowFeedback(false)} className="text-mute hover:text-ink">✕</button>
            </div>
            {feedback === undefined || loadingFeedback ? (
              <SkeletonText lines={6} />
            ) : feedback ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-mute">
                  <span>{feedback.model_version}</span>
                  <span>·</span>
                  <span>{new Date(feedback.generated_at).toLocaleDateString('ru')}</span>
                </div>
                <div className="surface rounded-2xl p-4">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h2: ({ children }) => <h2 className="font-semibold text-ink mt-3 mb-1 text-sm">{children}</h2>,
                      h3: ({ children }) => <h3 className="font-medium text-ink mt-2 mb-1 text-xs">{children}</h3>,
                      p: ({ children }) => <p className="text-ink/90 leading-relaxed mb-2 text-xs">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-2 text-xs text-ink/90">{children}</ul>,
                    }}
                  >
                    {feedback.suggestions_md}
                  </ReactMarkdown>
                </div>
                <button
                  onClick={requestFeedback}
                  disabled={loadingFeedback}
                  className="text-xs text-mute hover:text-accent transition-colors font-mono"
                >
                  ↻ обновить
                </button>
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="text-3xl mb-3">🤖</div>
                <p className="text-xs text-mute mb-4">Получи AI-анализ слабых мест</p>
                <button
                  onClick={requestFeedback}
                  disabled={loadingFeedback}
                  className="px-4 py-2 rounded-xl bg-accent text-[#06140d] text-xs font-semibold hover:bg-accentdk transition-colors disabled:opacity-60"
                >
                  {loadingFeedback ? 'Анализируем...' : 'Получить фидбэк'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
