'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { practice, type PracticeTask } from '@/lib/api'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { SkeletonText } from '@/components/ui/Skeleton'
import { useT } from '@/lib/i18n'

export default function PracticeTaskPage() {
  const { id } = useParams<{ id: string }>()
  const [task, setTask] = useState<PracticeTask | null>(null)
  const [loading, setLoading] = useState(true)
  const [solution, setSolution] = useState('')
  const t = useT()

  useEffect(() => {
    practice.getTask(id).then(setTask).finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return <div className="max-w-3xl mx-auto px-5 py-8"><SkeletonText lines={8} /></div>
  }

  if (!task) {
    return <div className="max-w-3xl mx-auto px-5 py-16 text-center text-mute">{t('practice.notFound')}</div>
  }

  return (
    <div className="max-w-3xl mx-auto px-5 py-8">
      <Link href={`/study/${task.study_session_id}`} className="text-sm text-mute hover:text-ink font-mono">{t('practice.back')}</Link>
      <div className="mt-6 mb-6">
        <div className="text-xs font-mono text-accent mb-2">{task.type}</div>
        <h1 className="font-display text-3xl font-bold text-ink">{task.title}</h1>
      </div>

      <div className="surface rounded-2xl p-5 mb-6 prose-grasp text-sm">
        <MarkdownRenderer>{task.instructions_md}</MarkdownRenderer>
      </div>

      {/* Solution editor */}
      <div className="surface rounded-2xl p-5 mb-6">
        <label className="text-xs font-mono text-mute mb-2 block">
          {t('practice.submit')}
        </label>
        <textarea
          rows={8}
          value={solution}
          onChange={(e) => setSolution(e.target.value)}
          placeholder={t('practice.submitHint')}
          className="w-full resize-y rounded-xl border border-line bg-card text-ink placeholder:text-mute/50 px-4 py-3 text-sm font-mono focus:outline-none focus:border-accent/60 transition-colors"
        />
        <button
          disabled
          className="mt-3 px-4 py-2 rounded-xl bg-accent text-[#06140d] text-sm font-semibold hover:bg-accentdk transition-colors disabled:opacity-50"
        >
          {t('practice.submit')}
        </button>
      </div>
    </div>
  )
}
