'use client'

import { useEffect, useState } from 'react'
import type { ChatAttachment } from '@/lib/api'

// File types accepted by the chat composer: code/text + pdf + images.
export const CHAT_ACCEPT =
  '.md,.py,.java,.csv,.txt,.js,.ts,.go,.rs,.c,.cpp,.h,.json,.yaml,.yml,.toml,.sh,.sql,.rb,.php,.kt,.pdf,.png,.jpg,.jpeg,.webp,.gif'

export const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'gif']

// ── File type metadata ──────────────────────────────────────────────────────
export const FILE_TYPES: Record<string, { color: string; bg: string; label: string }> = {
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

export function getFileType(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  return FILE_TYPES[ext] ?? FILE_DEFAULT
}

export function isImageName(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  return IMAGE_EXTENSIONS.includes(ext)
}

export function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

// ── File chip (text/code/pdf) ─────────────────────────────────────────────────
export function FileChip({
  name,
  size,
  onRemove,
}: {
  name: string
  size?: number
  onRemove?: () => void
}) {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  const ft = getFileType(name)

  return (
    <div
      className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border transition-all group max-w-[220px]"
      style={{ borderColor: `${ft.color}40`, background: ft.bg }}
    >
      <div
        className="w-6 h-6 rounded-md flex items-center justify-center text-[9px] font-bold font-mono shrink-0"
        style={{ background: ft.bg, color: ft.color, border: `1px solid ${ft.color}50` }}
      >
        {ext.toUpperCase().slice(0, 3)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-ink truncate leading-tight">{name}</p>
        {size != null && <p className="text-[10px] text-mute leading-tight">{formatSize(size)}</p>}
      </div>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove() }}
          className="text-mute hover:text-danger transition-all shrink-0"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      )}
    </div>
  )
}

// ── Pending attachment chip (composer): image thumbnail or file chip ──────────
export function PendingChip({ file, onRemove }: { file: File; onRemove: () => void }) {
  const [preview, setPreview] = useState<string | null>(null)

  useEffect(() => {
    if (!isImageName(file.name)) return
    const url = URL.createObjectURL(file)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  if (preview) {
    return (
      <div className="relative group w-14 h-14 rounded-lg overflow-hidden border border-line shrink-0">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={preview} alt={file.name} className="w-full h-full object-cover" />
        <button
          type="button"
          onClick={onRemove}
          className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-black/60 text-white flex items-center justify-center"
        >
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
    )
  }
  return <FileChip name={file.name} size={file.size} onRemove={onRemove} />
}

// ── Rendered (persisted) attachment in a message bubble ───────────────────────
export function MessageAttachment({ att }: { att: ChatAttachment }) {
  if (att.kind === 'image' && att.data_url) {
    return (
      <a href={att.data_url} target="_blank" rel="noreferrer" className="block">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={att.data_url}
          alt={att.name}
          className="max-w-[220px] max-h-[220px] rounded-lg border border-line object-cover"
        />
      </a>
    )
  }
  return <FileChip name={att.name} size={att.file_size ?? undefined} />
}
