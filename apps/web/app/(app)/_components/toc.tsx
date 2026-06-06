'use client'

export type Heading = { level: 2 | 3; text: string; id: string }

export function extractHeadings(md: string): Heading[] {
  const result: Heading[] = []
  for (const line of md.split('\n')) {
    const m2 = line.match(/^##\s+(.+)/)
    if (m2) { result.push({ level: 2, text: m2[1].trim(), id: slugify(m2[1].trim()) }); continue }
    const m3 = line.match(/^###\s+(.+)/)
    if (m3) result.push({ level: 3, text: m3[1].trim(), id: slugify(m3[1].trim()) })
  }
  return result
}

function slugify(text: string) {
  return text.toLowerCase().replace(/[^\wа-яё]/gi, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')
}

interface Props {
  headings: Heading[]
  activeId: string
  onClose?: () => void
}

export function ConspectToc({ headings, activeId, onClose }: Props) {
  if (headings.length === 0) return null

  return (
    <nav className="flex flex-col gap-0.5">
      {headings.map((h) => (
        <a
          key={h.id}
          href={`#${h.id}`}
          onClick={onClose}
          className={`
            block text-xs leading-snug rounded-lg px-2 py-1 transition-colors truncate
            ${h.level === 3 ? 'pl-4 text-mute/80' : 'font-medium'}
            ${activeId === h.id
              ? 'bg-accentsoft text-accent'
              : 'text-mute hover:text-ink hover:bg-card'}
          `}
        >
          {h.text}
        </a>
      ))}
    </nav>
  )
}
