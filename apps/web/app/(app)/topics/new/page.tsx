'use client'

import { useCallback, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { getStoredUser } from '@/lib/auth'
import { topics } from '@/lib/api'

const ACCEPT = '.md,.py,.java,.csv,.txt,.js,.ts,.go,.rs,.c,.cpp,.h,.json,.yaml,.yml,.toml,.sh,.sql,.rb,.php,.kt,.pdf'

const SUGGESTIONS = [
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

// ── File type metadata ──────────────────────────────────────────────────────
const FILE_TYPES: Record<string, { color: string; bg: string; label: string }> = {
  py:   { color: '#3776AB', bg: 'rgba(55,118,171,.15)',  label: 'Python' },
  js:   { color: '#F7DF1E', bg: 'rgba(247,223,30,.15)',  label: 'JS' },
  ts:   { color: '#3178C6', bg: 'rgba(49,120,198,.15)',  label: 'TS' },
  go:   { color: '#00ADD8', bg: 'rgba(0,173,216,.15)',   label: 'Go' },
  java: { color: '#F89820', bg: 'rgba(248,152,32,.15)',  label: 'Java' },
  rs:   { color: '#CE422B', bg: 'rgba(206,66,43,.15)',   label: 'Rust' },
  kt:   { color: '#7F52FF', bg: 'rgba(127,82,255,.15)',  label: 'Kotlin' },
  rb:   { color: '#CC342D', bg: 'rgba(204,52,45,.15)',   label: 'Ruby' },
  php:  { color: '#777BB4', bg: 'rgba(119,123,180,.15)', label: 'PHP' },
  md:   { color: '#A855F7', bg: 'rgba(168,85,247,.15)',  label: 'MD' },
  pdf:  { color: '#EF4444', bg: 'rgba(239,68,68,.15)',   label: 'PDF' },
  csv:  { color: '#10B981', bg: 'rgba(16,185,129,.15)',  label: 'CSV' },
  json: { color: '#F59E0B', bg: 'rgba(245,158,11,.15)',  label: 'JSON' },
  yaml: { color: '#8B5CF6', bg: 'rgba(139,92,246,.15)',  label: 'YAML' },
  yml:  { color: '#8B5CF6', bg: 'rgba(139,92,246,.15)',  label: 'YAML' },
  sql:  { color: '#3B82F6', bg: 'rgba(59,130,246,.15)',  label: 'SQL' },
  sh:   { color: '#6B7280', bg: 'rgba(107,114,128,.15)', label: 'SH' },
  toml: { color: '#9CA3AF', bg: 'rgba(156,163,175,.15)', label: 'TOML' },
}
const FILE_DEFAULT = { color: 'rgb(var(--accent))', bg: 'rgba(61,220,145,.12)', label: 'TXT' }

function getFileType(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  return FILE_TYPES[ext] ?? FILE_DEFAULT
}

// ── Types ───────────────────────────────────────────────────────────────────
type PendingFile = { id: string; file: File; name: string }
type PendingLink = { id: string; url: string; title: string }
type Pending = { files: PendingFile[]; links: PendingLink[] }

// ── Submitting steps ─────────────────────────────────────────────────────────
const STEPS = [
  'Создаём тему',
  'Загружаем файлы',
  'Сохраняем ссылки',
  'Читаем материалы',
  'Финальная сборка',
]

// ── Main page ────────────────────────────────────────────────────────────────
export default function NewTopicPage() {
  const router = useRouter()
  const user = getStoredUser()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [name, setName] = useState('')
  const [pending, setPending] = useState<Pending>({ files: [], links: [] })
  const [linkUrl, setLinkUrl] = useState('')
  const [showLinkInput, setShowLinkInput] = useState(false)
  const [dragOver, setDragOver] = useState(false)

  const [submitting, setSubmitting] = useState(false)
  const [submitStep, setSubmitStep] = useState(0)
  const [error, setError] = useState('')

  const totalMaterials = pending.files.length + pending.links.length

  // ── Add pending file ──────────────────────────────────────────────────────
  const addFile = useCallback((file: File) => {
    setPending((p) => ({
      ...p,
      files: [...p.files, { id: crypto.randomUUID(), file, name: file.name }],
    }))
  }, [])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    Array.from(e.target.files ?? []).forEach(addFile)
    e.target.value = ''
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    Array.from(e.dataTransfer.files).forEach(addFile)
  }

  const removeFile = (id: string) =>
    setPending((p) => ({ ...p, files: p.files.filter((f) => f.id !== id) }))

  // ── Add pending link ──────────────────────────────────────────────────────
  const handleAddLink = (e: React.FormEvent) => {
    e.preventDefault()
    const url = linkUrl.trim()
    if (!url) return
    const title = (() => {
      try { return new URL(url).hostname } catch { return url }
    })()
    setPending((p) => ({
      ...p,
      links: [...p.links, { id: crypto.randomUUID(), url, title }],
    }))
    setLinkUrl('')
    setShowLinkInput(false)
  }

  const removeLink = (id: string) =>
    setPending((p) => ({ ...p, links: p.links.filter((l) => l.id !== id) }))

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !user) return
    setSubmitting(true)
    setError('')
    setSubmitStep(0)

    try {
      // Step 1 — create topic
      const topic = await topics.start(user.user_id, name.trim())
      setSubmitStep(1)

      // Step 2 — upload files
      for (const pf of pending.files) {
        await topics.uploadFile(topic.id, user.user_id, pf.file)
      }
      setSubmitStep(2)

      // Step 3 — add links
      for (const pl of pending.links) {
        await topics.addLink(topic.id, user.user_id, pl.url)
      }
      setSubmitStep(3)

      router.push(`/topics/${topic.id}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ошибка создания темы')
      setSubmitting(false)
      setSubmitStep(0)
    }
  }

  if (submitting) {
    return <SubmittingScreen step={submitStep} name={name} total={totalMaterials} />
  }

  return (
    <div className="max-w-2xl mx-auto px-5 py-10">
      {/* Back */}
      <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink transition-colors mb-8 font-mono">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="15 18 9 12 15 6"/></svg>
        Dashboard
      </Link>

      <form onSubmit={handleSubmit}>
        {/* ── Header ───────────────────────────────────────────────────────── */}
        <div className="mb-8">
          <h1 className="font-display text-3xl sm:text-4xl font-bold text-ink leading-tight mb-6">
            Новая тема
          </h1>

          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Название темы — например, Go горутины и каналы"
            required
            autoFocus
            maxLength={120}
            className="w-full px-4 py-3.5 rounded-xl border border-line bg-card text-ink placeholder:text-mute/40 focus:outline-none focus:border-accent/60 transition-colors text-base font-medium"
          />

          {/* Quick suggestions */}
          <div className="flex flex-wrap gap-1.5 mt-3">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setName(s)}
                className="px-2.5 py-1 rounded-lg border border-line text-xs text-mute hover:text-ink hover:border-accent/40 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* ── Materials zone ───────────────────────────────────────────────── */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="text-sm font-medium text-ink">Материалы для изучения</span>
              <span className="text-xs text-mute ml-2 font-mono">необязательно</span>
            </div>
            {totalMaterials > 0 && (
              <span className="text-xs font-mono text-accent">
                {totalMaterials} добавлено
              </span>
            )}
          </div>

          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`relative border-2 border-dashed rounded-2xl transition-all cursor-pointer select-none ${
              dragOver
                ? 'border-accent bg-accentsoft/40 scale-[1.01]'
                : 'border-line hover:border-mute/60 hover:bg-card/60'
            } ${totalMaterials > 0 ? 'p-4' : 'p-10'}`}
          >
            {totalMaterials === 0 ? (
              /* Empty state */
              <div className="flex flex-col items-center gap-3 text-center pointer-events-none">
                <div className="w-12 h-12 rounded-2xl bg-card border border-line flex items-center justify-center">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--mute))" strokeWidth="1.5">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-ink">Перетащи файлы сюда</p>
                  <p className="text-xs text-mute mt-1">
                    .py, .go, .java, .md, .pdf, .csv, .ts и другие
                  </p>
                </div>
              </div>
            ) : (
              /* Files grid */
              <div className="grid sm:grid-cols-2 gap-2" onClick={(e) => e.stopPropagation()}>
                {pending.files.map((pf) => (
                  <FileChip key={pf.id} name={pf.name} size={pf.file.size} onRemove={() => removeFile(pf.id)} />
                ))}
                {pending.links.map((pl) => (
                  <LinkChip key={pl.id} url={pl.url} title={pl.title} onRemove={() => removeLink(pl.id)} />
                ))}
                {/* Add more hint */}
                <div className="flex items-center gap-2 px-3 py-2 rounded-xl border border-dashed border-line text-xs text-mute col-span-full sm:col-span-1">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  Добавить ещё файлы
                </div>
              </div>
            )}

            {dragOver && (
              <div className="absolute inset-0 rounded-2xl flex items-center justify-center bg-accentsoft/60 pointer-events-none">
                <p className="text-accent font-semibold">Отпусти файлы</p>
              </div>
            )}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT}
            multiple
            className="hidden"
            onChange={handleFileChange}
          />

          {/* Actions row */}
          <div className="flex items-center gap-2 mt-2">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-line bg-card text-xs text-mute hover:text-ink hover:border-accent/40 transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              Файл
            </button>
            <button
              type="button"
              onClick={() => setShowLinkInput((v) => !v)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-line bg-card text-xs text-mute hover:text-ink hover:border-accent/40 transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
              Ссылка
            </button>
            <span className="text-xs text-mute ml-auto">.py .go .java .md .pdf .csv .ts ...</span>
          </div>

          {showLinkInput && (
            <div className="mt-2 flex gap-2">
              <input
                type="url"
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                placeholder="https://..."
                autoFocus
                className="flex-1 px-3 py-2 rounded-xl border border-line bg-card text-sm text-ink placeholder:text-mute/50 focus:outline-none focus:border-accent/60 transition-colors"
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddLink(e as unknown as React.FormEvent) } }}
              />
              <button
                type="button"
                onClick={handleAddLink}
                disabled={!linkUrl.trim()}
                className="px-3 py-2 rounded-xl bg-accent text-[#06140d] text-sm font-semibold hover:bg-accentdk transition-colors disabled:opacity-40"
              >
                ОК
              </button>
              <button
                type="button"
                onClick={() => { setShowLinkInput(false); setLinkUrl('') }}
                className="px-3 py-2 rounded-xl border border-line text-mute text-sm hover:text-ink transition-colors"
              >
                ✕
              </button>
            </div>
          )}
        </div>

        {/* ── Error ────────────────────────────────────────────────────────── */}
        {error && (
          <p className="mb-4 px-4 py-3 rounded-xl bg-danger/10 border border-danger/20 text-sm text-danger">{error}</p>
        )}

        {/* ── Submit ───────────────────────────────────────────────────────── */}
        <button
          type="submit"
          disabled={!name.trim() || submitting}
          className="w-full py-4 rounded-xl bg-accent text-[#06140d] font-semibold text-base hover:bg-accentdk transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {submitting
            ? 'Создаём...'
            : totalMaterials > 0
            ? `Создать тему с материалами (${totalMaterials}) →`
            : 'Создать тему →'}
        </button>
        {totalMaterials === 0 && (
          <p className="text-center text-xs text-mute mt-3">
            Материалы можно добавить сейчас или после создания темы
          </p>
        )}
      </form>
    </div>
  )
}

// ── File chip ─────────────────────────────────────────────────────────────────
function FileChip({ name, size, onRemove }: { name: string; size: number; onRemove: () => void }) {
  const ft = getFileType(name)
  const ext = name.split('.').pop()?.toLowerCase() ?? ''

  return (
    <div
      className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl border transition-all group"
      style={{ borderColor: `${ft.color}40`, background: ft.bg }}
    >
      {/* Type badge */}
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold font-mono shrink-0"
        style={{ background: ft.bg, color: ft.color, border: `1px solid ${ft.color}50` }}
      >
        {ext.toUpperCase().slice(0, 3)}
      </div>

      {/* Name + size */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-ink truncate leading-tight">{name}</p>
        <p className="text-xs text-mute mt-0.5">{formatSize(size)}</p>
      </div>

      {/* Remove */}
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onRemove() }}
        className="text-mute opacity-0 group-hover:opacity-100 hover:text-danger transition-all shrink-0"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  )
}

// ── Link chip ─────────────────────────────────────────────────────────────────
function LinkChip({ url, title, onRemove }: { url: string; title: string; onRemove: () => void }) {
  const domain = (() => { try { return new URL(url).hostname.replace('www.', '') } catch { return url } })()

  return (
    <div
      className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl border border-accent/30 group transition-all"
      style={{ background: 'rgba(61,220,145,.08)' }}
    >
      {/* Icon */}
      <div className="w-8 h-8 rounded-lg bg-accentsoft border border-accent/30 flex items-center justify-center shrink-0">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
          <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/>
          <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/>
        </svg>
      </div>

      {/* Domain + url */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-ink truncate leading-tight">{title}</p>
        <p className="text-xs text-mute truncate mt-0.5">{domain}</p>
      </div>

      {/* Remove */}
      <button
        type="button"
        onClick={onRemove}
        className="text-mute opacity-0 group-hover:opacity-100 hover:text-danger transition-all shrink-0"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  )
}

// ── Submitting overlay ────────────────────────────────────────────────────────
function SubmittingScreen({ step, name, total }: { step: number; name: string; total: number }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-5 py-12">
      <div className="w-full max-w-sm text-center">
        <div className="w-14 h-14 rounded-2xl bg-accentsoft flex items-center justify-center mx-auto mb-5">
          <div className="w-7 h-7 rounded-full border-2 border-accentdk border-t-accent animate-spin" />
        </div>
        <h2 className="font-display text-xl font-bold text-ink mb-1">Создаём тему</h2>
        <p className="text-mute text-sm mb-6 font-mono truncate">«{name}»</p>
        <div className="space-y-1.5 text-left">
          {STEPS.slice(0, total > 0 ? 3 : 1).map((s, i) => {
            const done = i < step
            const active = i === step
            return (
              <div key={s} className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all ${active ? 'bg-accentsoft' : ''}`}>
                <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 ${done ? 'bg-accent' : active ? 'border-2 border-accent' : 'border border-line'}`}>
                  {done && <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="#06140d" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>}
                </div>
                <span className={`text-sm ${active ? 'text-accent font-medium' : done ? 'text-mute' : 'text-mute/50'}`}>{s}</span>
              </div>
            )
          })}
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
