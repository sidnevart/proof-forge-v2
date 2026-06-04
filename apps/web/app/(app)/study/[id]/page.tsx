'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getStoredUser } from '@/lib/auth'
import { practice, type PracticeTask, type StudySession } from '@/lib/api'
import { SkeletonText } from '@/components/ui/Skeleton'

export default function StudySessionPage() {
  const { id } = useParams<{ id: string }>()
  const user = getStoredUser()
  const [session, setSession] = useState<StudySession | null>(null)
  const [tasks, setTasks] = useState<PracticeTask[]>([])
  const [loading, setLoading] = useState(true)
  const [completing, setCompleting] = useState(false)

  useEffect(() => {
    if (!user) return
    Promise.all([
      practice.getSession(id),
      practice.listActiveTasks(user.user_id),
    ]).then(([s, active]) => {
      setSession(s)
      setTasks(active.filter((task) => task.study_session_id === s.id))
    }).finally(() => setLoading(false))
  }, [id, user?.user_id])

  const handleComplete = async () => {
    if (!user || !session) return
    setCompleting(true)
    try {
      const result = await practice.completeSession(session.id, user.user_id)
      window.location.href = `/capsule/${result.capsule.id}`
    } finally {
      setCompleting(false)
    }
  }

  if (loading) {
    return <div className="max-w-3xl mx-auto px-5 py-8"><SkeletonText lines={8} /></div>
  }

  if (!session) {
    return <div className="max-w-3xl mx-auto px-5 py-16 text-center text-mute">Сессия не найдена</div>
  }

  return (
    <div className="max-w-3xl mx-auto px-5 py-8">
      <Link href="/dashboard" className="text-sm text-mute hover:text-ink font-mono">← назад</Link>
      <div className="mt-6 mb-8">
        <div className="text-xs font-mono text-accent mb-2">Учебная сессия</div>
        <h1 className="font-display text-3xl font-bold text-ink">Конспект и практика</h1>
      </div>

      <section className="prose-grasp mb-8">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{session.conspect_md}</ReactMarkdown>
      </section>

      <section>
        <h2 className="text-sm font-mono text-mute mb-3">Задания</h2>
        <div className="space-y-3">
          {tasks.map((task) => (
            <Link key={task.id} href={`/practice/${task.id}`} className="surface surface-hover rounded-xl p-4 block">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-xs font-mono text-accent mb-1">{task.type}</div>
                  <div className="font-semibold text-ink">{task.title}</div>
                  <div className="text-sm text-mute mt-1">{task.target_concepts.join(', ')}</div>
                </div>
                <span className="text-xs font-mono text-mute">{task.status}</span>
              </div>
            </Link>
          ))}
        </div>
        <button
          onClick={handleComplete}
          disabled={completing}
          className="mt-8 w-full py-3 rounded-xl bg-accent text-[#06140d] font-semibold text-sm hover:bg-accentdk transition-colors disabled:opacity-50"
        >
          {completing ? 'Форжим капсулу...' : 'Завершить сегмент и создать капсулу →'}
        </button>
      </section>
    </div>
  )
}
