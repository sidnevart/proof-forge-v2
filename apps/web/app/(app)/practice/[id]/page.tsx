'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { practice, type PracticeTask } from '@/lib/api'
import { SkeletonText } from '@/components/ui/Skeleton'
import { useT } from '@/lib/i18n'

export default function PracticeTaskPage() {
  const { id } = useParams<{ id: string }>()
  const [task, setTask] = useState<PracticeTask | null>(null)
  const [loading, setLoading] = useState(true)
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
        <div className="text-xs font-mono text-accent mb-2">IDE task</div>
        <h1 className="font-display text-3xl font-bold text-ink">{task.title}</h1>
        <p className="text-sm text-mute mt-2 font-mono">status: {task.status}</p>
      </div>

      <div className="surface rounded-2xl p-5 mb-6">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.instructions_md}</ReactMarkdown>
      </div>

      <div className="grid sm:grid-cols-2 gap-3 mb-6">
        <div className="surface rounded-xl p-4">
          <div className="text-xs font-mono text-mute mb-2">{t('practice.evidence')}</div>
          <ul className="text-sm text-ink space-y-1">
            {task.expected_evidence.map((item) => <li key={item}>• {item}</li>)}
          </ul>
        </div>
        <div className="surface rounded-xl p-4">
          <div className="text-xs font-mono text-mute mb-2">{t('practice.commands')}</div>
          {task.check_commands.length
            ? task.check_commands.map((cmd) => <code key={cmd} className="block text-sm text-ink">{cmd}</code>)
            : <p className="text-sm text-mute">{t('practice.commandsEmpty')}</p>
          }
        </div>
      </div>

      <div className="surface rounded-2xl p-5 border border-accent/20 bg-accentsoft/20">
        <div className="font-semibold text-ink mb-1">Submit from JetBrains</div>
        <p className="text-sm text-mute">
          Open the Proof Forge plugin in JetBrains, select this task, and submit files, diff, test output, and reflection.
        </p>
      </div>
    </div>
  )
}
