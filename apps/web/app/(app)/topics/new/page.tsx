'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { getStoredUser } from '@/lib/auth'
import { topics } from '@/lib/api'

const TOPIC_SUGGESTIONS = [
  'Go горутины и каналы',
  'Docker и контейнеризация',
  'Kubernetes основы',
  'System Design: распределённые системы',
  'SQL оптимизация запросов',
  'React хуки и жизненный цикл',
  'gRPC vs REST',
  'CAP-теорема',
  'Kafka: устройство и паттерны',
  'PostgreSQL индексы',
]

type Phase = 'input' | 'generating' | 'error'

export default function NewTopicPage() {
  const router = useRouter()
  const user = getStoredUser()
  const [topic, setTopic] = useState('')
  const [description, setDescription] = useState('')
  const [phase, setPhase] = useState<Phase>('input')
  const [error, setError] = useState('')
  const [generatingStep, setGeneratingStep] = useState(0)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!topic.trim() || !user) return

    setPhase('generating')
    setError('')

    // Animate progress through steps
    const stepInterval = setInterval(() => {
      setGeneratingStep((s) => (s < 3 ? s + 1 : s))
    }, 2200)

    try {
      const result = await topics.generateWeb(user.user_id, topic.trim(), description.trim())
      clearInterval(stepInterval)
      router.push(`/capsule/${result.capsule_id}`)
    } catch (err: unknown) {
      clearInterval(stepInterval)
      setError(err instanceof Error ? err.message : 'Ошибка генерации')
      setPhase('error')
      setGeneratingStep(0)
    }
  }

  const useSuggestion = (s: string) => {
    setTopic(s)
    setDescription('')
  }

  if (phase === 'generating') {
    return <GeneratingScreen step={generatingStep} topic={topic} />
  }

  return (
    <div className="max-w-xl mx-auto px-5 py-10">
      {/* Back */}
      <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink transition-colors mb-8 font-mono">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="15 18 9 12 15 6"/></svg>
        На главную
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 text-xs font-mono text-accent bg-accentsoft border border-accent/20 rounded-full px-3 py-1 mb-4">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          AI-генерация капсулы
        </div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-ink leading-tight">
          Что будем<br />изучать?
        </h1>
        <p className="text-mute mt-3">
          Введи тему — AI создаст структурированный материал и карточки для повторения.
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-mute mb-2">Тема</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Например: Go горутины и каналы"
            required
            autoFocus
            maxLength={120}
            className="w-full px-4 py-3.5 rounded-xl border border-line bg-card text-ink placeholder:text-mute/50 focus:outline-none focus:border-accent/60 transition-colors text-base"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-mute mb-2">
            Контекст <span className="text-mute/60 font-normal">(необязательно)</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Что уже знаешь? Зачем изучаешь? Какой уровень? — AI адаптирует материал"
            rows={2}
            maxLength={300}
            className="w-full px-4 py-3 rounded-xl border border-line bg-card text-ink placeholder:text-mute/50 focus:outline-none focus:border-accent/60 transition-colors resize-none text-sm"
          />
        </div>

        {phase === 'error' && (
          <div className="px-4 py-3 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={!topic.trim()}
          className="w-full py-4 rounded-xl bg-accent text-[#06140d] font-semibold text-base hover:bg-accentdk transition-colors disabled:opacity-40 disabled:cursor-not-allowed btn-press"
        >
          Создать капсулу →
        </button>

        <p className="text-center text-xs text-mute">~30 секунд · AI напишет теорию и 6 карточек</p>
      </form>

      {/* Suggestions */}
      <div className="mt-10">
        <p className="text-xs font-mono text-mute mb-3 tracking-wide uppercase">Популярные темы</p>
        <div className="flex flex-wrap gap-2">
          {TOPIC_SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => useSuggestion(s)}
              className="px-3 py-1.5 rounded-lg border border-line bg-card text-sm text-mute hover:text-ink hover:border-accent/40 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

const STEPS = [
  { label: 'Анализирую тему', icon: '🔍' },
  { label: 'Пишу теорию и примеры', icon: '📝' },
  { label: 'Составляю карточки', icon: '🃏' },
  { label: 'Финальная сборка', icon: '⚗️' },
]

function GeneratingScreen({ step, topic }: { step: number; topic: string }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-5 py-12">
      <div className="w-full max-w-sm text-center">
        <div className="w-16 h-16 rounded-2xl bg-accentsoft flex items-center justify-center mx-auto mb-6">
          <div className="w-8 h-8 rounded-full border-2 border-accentdk border-t-accent animate-spin" />
        </div>
        <h2 className="font-display text-2xl font-bold text-ink mb-1">Создаю капсулу</h2>
        <p className="text-mute text-sm mb-8 font-mono truncate max-w-xs mx-auto">«{topic}»</p>

        {/* Steps */}
        <div className="space-y-2 text-left">
          {STEPS.map((s, i) => {
            const done = i < step
            const active = i === step
            return (
              <div
                key={s.label}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all ${
                  active ? 'bg-accentsoft border border-accent/30' : done ? 'opacity-50' : 'opacity-30'
                }`}
              >
                <span className="text-base w-6 text-center">
                  {done ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2.5">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  ) : (
                    s.icon
                  )}
                </span>
                <span className={`text-sm font-medium ${active ? 'text-accent' : done ? 'text-mute' : 'text-mute'}`}>
                  {s.label}
                </span>
                {active && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />}
              </div>
            )
          })}
        </div>

        <p className="mt-8 text-xs text-mute">Обычно занимает 20–40 секунд</p>
      </div>
    </div>
  )
}
