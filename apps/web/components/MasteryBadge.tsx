'use client'

type Level = 'unknown' | 'recognize' | 'apply' | 'explain'

const LABELS: Record<Level, string> = {
  unknown: 'Не изучено',
  recognize: 'Узнаю',
  apply: 'Применяю',
  explain: 'Объясню',
}

const ICONS: Record<Level, string> = {
  unknown: '○',
  recognize: '◐',
  apply: '●',
  explain: '★',
}

export function MasteryBadge({ level, concept, size = 'md' }: {
  level: Level
  concept?: string
  size?: 'sm' | 'md' | 'lg'
}) {
  const sizeClass = size === 'sm' ? 'text-xs px-2 py-0.5' : size === 'lg' ? 'text-sm px-3 py-1.5' : 'text-xs px-2.5 py-1'

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-lg border font-mono font-medium badge-${level} ${sizeClass}`}
      title={LABELS[level]}
    >
      <span>{ICONS[level]}</span>
      {concept && <span className="font-sans">{concept}</span>}
      {!concept && <span>{LABELS[level]}</span>}
    </span>
  )
}

export function MasteryDot({ level }: { level: Level }) {
  const colors: Record<Level, string> = {
    unknown: 'bg-mute/40',
    recognize: 'bg-yellow-400',
    apply: 'bg-accent',
    explain: 'bg-blue-400',
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[level]}`} title={LABELS[level]} />
}
