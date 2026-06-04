'use client'

import { useEffect, useState } from 'react'
import { use } from 'react'
import { capsules, type Capsule, type CapsuleFeedback } from '@/lib/api'
import { getStoredUser } from '@/lib/auth'
import { track } from '@/lib/analytics'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Skeleton, SkeletonText } from '@/components/ui/Skeleton'
import Link from 'next/link'

export default function CapsulePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const user = getStoredUser()
  const [capsule, setCapsule] = useState<Capsule | null>(null)
  const [feedback, setFeedback] = useState<CapsuleFeedback | null | undefined>(undefined)
  const [loadingFeedback, setLoadingFeedback] = useState(false)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'content' | 'questions' | 'feedback'>('content')

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

  const requestFeedback = async () => {
    if (!user) return
    setLoadingFeedback(true)
    track({ name: 'ai_feedback_clicked', props: { capsule_id: id } })
    try {
      const f = await capsules.requestFeedback(id)
      setFeedback(f)
      setActiveTab('feedback')
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingFeedback(false)
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

  return (
    <div className="max-w-2xl mx-auto px-5 py-8">
      {/* Back */}
      <Link href="/dashboard" className="flex items-center gap-1.5 text-sm text-mute hover:text-ink transition-colors mb-6 font-mono">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
        назад
      </Link>

      {/* Header */}
      <div className="mb-6">
        <div className="text-xs font-mono text-accent mb-2">Капсула знаний</div>
        <h1 className="font-display text-2xl sm:text-3xl font-bold text-ink leading-tight">{capsule.summary}</h1>
        <p className="text-sm text-mute mt-2 font-mono">
          {new Date(capsule.created_at).toLocaleDateString('ru', { day: 'numeric', month: 'long', year: 'numeric' })}
          {' · '}{capsule.review_questions.length} вопросов
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-sand rounded-xl mb-6 border border-line">
        {([['content', 'Материал'], ['questions', `Вопросы (${capsule.review_questions.length})`], ['feedback', 'AI-фидбэк']] as const).map(([tab, label]) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab
                ? 'bg-card text-ink shadow-sm border border-line'
                : 'text-mute hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Content tab */}
      {activeTab === 'content' && (
        <div className="prose-grasp">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({children}) => <h1 className="font-display text-2xl font-bold text-ink mt-6 mb-3">{children}</h1>,
              h2: ({children}) => <h2 className="font-display text-xl font-bold text-ink mt-5 mb-2">{children}</h2>,
              h3: ({children}) => <h3 className="font-semibold text-ink mt-4 mb-2">{children}</h3>,
              p: ({children}) => <p className="text-ink/90 leading-relaxed mb-3">{children}</p>,
              code: ({children, className}) => className
                ? <code className="code-surface block p-4 rounded-xl font-mono text-sm my-3 overflow-x-auto whitespace-pre">{children}</code>
                : <code className="font-mono text-accent bg-accentsoft px-1.5 py-0.5 rounded text-sm">{children}</code>,
              ul: ({children}) => <ul className="list-disc list-inside space-y-1 mb-3 text-ink/90">{children}</ul>,
              ol: ({children}) => <ol className="list-decimal list-inside space-y-1 mb-3 text-ink/90">{children}</ol>,
              blockquote: ({children}) => (
                <blockquote className="border-l-2 border-accent pl-4 my-3 text-mute italic">{children}</blockquote>
              ),
            }}
          >
            {capsule.content_md}
          </ReactMarkdown>
        </div>
      )}

      {/* Questions tab */}
      {activeTab === 'questions' && (
        <div className="space-y-3">
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
      )}

      {/* Feedback tab */}
      {activeTab === 'feedback' && (
        <div>
          {feedback === undefined || loadingFeedback ? (
            <SkeletonText lines={6} />
          ) : feedback ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-xs font-mono text-mute">
                <span>AI-фидбэк</span>
                <span>·</span>
                <span>{new Date(feedback.generated_at).toLocaleDateString('ru')}</span>
                <span>·</span>
                <span>{feedback.model_version}</span>
              </div>
              <div className="surface rounded-2xl p-5">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h2: ({children}) => <h2 className="font-semibold text-ink mt-4 mb-2">{children}</h2>,
                    h3: ({children}) => <h3 className="font-medium text-ink mt-3 mb-1">{children}</h3>,
                    p: ({children}) => <p className="text-ink/90 leading-relaxed mb-2 text-sm">{children}</p>,
                    ul: ({children}) => <ul className="list-disc list-inside space-y-1 mb-2 text-sm text-ink/90">{children}</ul>,
                    li: ({children}) => <li className="text-ink/90">{children}</li>,
                  }}
                >
                  {feedback.suggestions_md}
                </ReactMarkdown>
              </div>
              <button
                onClick={requestFeedback}
                disabled={loadingFeedback}
                className="text-sm text-mute hover:text-accent transition-colors font-mono"
              >
                ↻ обновить фидбэк
              </button>
            </div>
          ) : (
            <div className="text-center py-10">
              <div className="text-4xl mb-4">🤖</div>
              <h3 className="font-display text-xl font-bold text-ink mb-2">Получи AI-анализ</h3>
              <p className="text-mute text-sm max-w-xs mx-auto mb-6">
                Claude проанализирует твои слабые места и даст конкретные рекомендации что подтянуть.
              </p>
              <button
                onClick={requestFeedback}
                disabled={loadingFeedback}
                className="px-6 py-3 rounded-xl bg-accent text-[#06140d] font-semibold hover:bg-accentdk transition-colors disabled:opacity-60"
              >
                {loadingFeedback ? 'Анализируем...' : 'Получить фидбэк →'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
