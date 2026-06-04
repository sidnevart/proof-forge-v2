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

export default function NewTopicPage() {
  const router = useRouter()
  const user = getStoredUser()
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !user) return
    setLoading(true)
    setError('')
    try {
      const topic = await topics.start(user.user_id, name.trim())
      router.push(`/topics/${topic.id}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ошибка создания темы')
      setLoading(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto px-5 py-10">
      <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink transition-colors mb-8 font-mono">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="15 18 9 12 15 6"/></svg>
        На главную
      </Link>

      <div className="mb-8">
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-ink leading-tight">
          Новая тема
        </h1>
        <p className="text-mute mt-3">
          Дай теме название — потом добавишь материалы для изучения.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-mute mb-2">Название темы</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Например: Go горутины и каналы"
            required
            autoFocus
            maxLength={120}
            className="w-full px-4 py-3.5 rounded-xl border border-line bg-card text-ink placeholder:text-mute/50 focus:outline-none focus:border-accent/60 transition-colors text-base"
          />
        </div>

        {error && (
          <p className="px-4 py-3 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger">{error}</p>
        )}

        <button
          type="submit"
          disabled={!name.trim() || loading}
          className="w-full py-4 rounded-xl bg-accent text-[#06140d] font-semibold text-base hover:bg-accentdk transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? 'Создаём...' : 'Создать тему →'}
        </button>
      </form>

      <div className="mt-10">
        <p className="text-xs font-mono text-mute mb-3 tracking-wide uppercase">Популярные темы</p>
        <div className="flex flex-wrap gap-2">
          {TOPIC_SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setName(s)}
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
