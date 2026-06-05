'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { getStoredUser } from '@/lib/auth'
import { topics, practice, type Topic, type TopicMaterial } from '@/lib/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { track } from '@/lib/analytics'
import { useT, useLocale, ruPlural } from '@/lib/i18n'

const ACCEPT = '.md,.py,.java,.csv,.txt,.js,.ts,.go,.rs,.c,.cpp,.h,.json,.yaml,.yml,.toml,.sh,.sql,.rb,.php,.kt,.pdf'

export default function TopicPage() {
  const { id: topicId } = useParams<{ id: string }>()
  const router = useRouter()
  const user = getStoredUser()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const t = useT()
  const { locale } = useLocale()

  const [topic, setTopic] = useState<Topic | null>(null)
  const [materials, setMaterials] = useState<TopicMaterial[]>([])
  const [loadingTopic, setLoadingTopic] = useState(true)

  const [uploadingFile, setUploadingFile] = useState(false)
  const [linkUrl, setLinkUrl] = useState('')
  const [addingLink, setAddingLink] = useState(false)
  const [showLinkInput, setShowLinkInput] = useState(false)

  const [dragOver, setDragOver] = useState(false)

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

  const handleFileUpload = async (file: File) => {
    if (!user) return
    setUploadingFile(true)
    try {
      const mat = await topics.uploadFile(topicId, user.user_id, file)
      setMaterials((prev) => [...prev, mat])
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : t('topic.uploadError'))
    } finally {
      setUploadingFile(false)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFileUpload(file)
    e.target.value = ''
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFileUpload(file)
  }

  const handleAddLink = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!linkUrl.trim() || !user) return
    setAddingLink(true)
    try {
      const mat = await topics.addLink(topicId, user.user_id, linkUrl.trim())
      setMaterials((prev) => [...prev, mat])
      setLinkUrl('')
      setShowLinkInput(false)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : t('topic.addLinkError'))
    } finally {
      setAddingLink(false)
    }
  }

  const handleDelete = async (materialId: string) => {
    try {
      await topics.deleteMaterial(topicId, materialId)
      setMaterials((prev) => prev.filter((m) => m.id !== materialId))
    } catch {
      // ignore
    }
  }

  const handleStartStudy = async () => {
    if (!user || !topic) return
    setStartingStudy(true)
    setStudyError('')
    try {
      const result = await practice.startSession(user.user_id, topic.id)
      router.push(`/study/${result.session.id}`)
    } catch (err: unknown) {
      setStudyError(err instanceof Error ? err.message : t('topic.startError'))
    } finally {
      setStartingStudy(false)
    }
  }

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
      <div className="mb-8">
        <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-xs text-mute hover:text-ink transition-colors mb-4 font-mono">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="15 18 9 12 15 6"/></svg>
          Dashboard
        </Link>
        <h1 className="font-display text-2xl sm:text-3xl font-bold text-ink">{topic.name}</h1>
        <p className="text-sm text-mute font-mono mt-1">
          {materials.length === 0 ? t('topic.noMaterials') : materialsLabel}
        </p>
      </div>

      {/* Drop zone + add buttons */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-2xl p-6 mb-6 transition-all ${
          dragOver
            ? 'border-accent bg-accentsoft/30'
            : 'border-line hover:border-mute/60'
        }`}
      >
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadingFile}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-line bg-card text-sm font-medium text-ink hover:border-accent/40 hover:text-accent transition-colors disabled:opacity-50"
          >
            {uploadingFile ? (
              <div className="w-4 h-4 rounded-full border-2 border-line border-t-accent animate-spin" />
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            )}
            {uploadingFile ? t('topic.uploading') : t('topic.uploadFile')}
          </button>

          <button
            type="button"
            onClick={() => setShowLinkInput((v) => !v)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-line bg-card text-sm font-medium text-ink hover:border-accent/40 hover:text-accent transition-colors"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
            {t('topic.addLink')}
          </button>

          <p className="text-xs text-mute sm:ml-auto text-center sm:text-right">
            .md .py .pdf .csv .java<br className="hidden sm:block" /><span className="sm:hidden"> </span>and more
          </p>
        </div>

        {dragOver && (
          <p className="text-center text-sm text-accent mt-3 font-medium">{t('topic.dropRelease')}</p>
        )}

        {showLinkInput && (
          <form onSubmit={handleAddLink} className="mt-4 flex gap-2">
            <input
              type="url"
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              placeholder="https://..."
              required
              autoFocus
              className="flex-1 px-3 py-2.5 rounded-xl border border-line bg-card text-ink text-sm placeholder:text-mute/50 focus:outline-none focus:border-accent/60 transition-colors"
            />
            <button
              type="submit"
              disabled={addingLink || !linkUrl.trim()}
              className="px-4 py-2.5 rounded-xl bg-accent text-[#06140d] text-sm font-semibold hover:bg-accentdk transition-colors disabled:opacity-50"
            >
              {addingLink ? '...' : t('topic.add')}
            </button>
            <button
              type="button"
              onClick={() => setShowLinkInput(false)}
              className="px-3 py-2.5 rounded-xl border border-line text-mute hover:text-ink transition-colors text-sm"
            >
              ✕
            </button>
          </form>
        )}

        {materials.length === 0 && !showLinkInput && (
          <p className="text-center text-sm text-mute mt-4">{t('topic.dropHint')}</p>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Materials list */}
      {materials.length > 0 && (
        <div className="space-y-2 mb-8">
          {materials.map((m) => (
            <MaterialCard key={m.id} material={m} onDelete={() => handleDelete(m.id)} t={t} />
          ))}
        </div>
      )}

      {/* Study error */}
      {studyError && (
        <div className="mb-4 px-4 py-3 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger">
          {studyError}
        </div>
      )}

      <div className="surface rounded-2xl p-5 mb-6 border border-accent/20 bg-accentsoft/20">
        <div className="text-xs font-mono text-accent mb-1">New flow</div>
        <h2 className="font-display text-xl font-bold text-ink mb-2">{t('topic.study.title')}</h2>
        <p className="text-sm text-mute mb-4">{t('topic.study.desc')}</p>
        <button
          onClick={handleStartStudy}
          disabled={startingStudy}
          className="w-full py-3 rounded-xl bg-accent text-[#06140d] font-semibold text-sm hover:bg-accentdk transition-colors disabled:opacity-50"
        >
          {startingStudy ? t('topic.study.launching') : t('topic.study.cta')}
        </button>
      </div>

    </div>
  )
}

function MaterialCard({ material, onDelete, t }: { material: TopicMaterial; onDelete: () => void; t: (k: string) => string }) {
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

        <button
          type="button"
          onClick={onDelete}
          className="text-mute hover:text-danger transition-colors shrink-0 mt-0.5 p-1"
          title={t('topic.delete')}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
        </button>
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
