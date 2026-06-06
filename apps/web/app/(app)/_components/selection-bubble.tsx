'use client'

import { useEffect, useRef, useState } from 'react'

interface Props {
  containerRef: React.RefObject<HTMLElement | null>
  onAsk: (text: string) => void
}

export function SelectionBubble({ containerRef, onAsk }: Props) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)
  const [text, setText] = useState('')
  const bubbleRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleMouseUp = () => {
      // Small delay so selection is committed
      setTimeout(() => {
        const sel = window.getSelection()
        const selected = sel?.toString().trim() ?? ''
        if (!selected || selected.length < 3) { setPos(null); return }

        // Ensure selection is inside our container
        if (sel && sel.rangeCount > 0) {
          const range = sel.getRangeAt(0)
          if (!container.contains(range.commonAncestorContainer)) { setPos(null); return }

          const rect = range.getBoundingClientRect()
          const containerRect = container.getBoundingClientRect()
          setPos({
            x: rect.left + rect.width / 2 - containerRect.left,
            y: rect.top - containerRect.top - 44,
          })
          setText(selected)
        }
      }, 10)
    }

    const handleMouseDown = (e: MouseEvent) => {
      if (bubbleRef.current?.contains(e.target as Node)) return
      setPos(null)
    }

    container.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('mousedown', handleMouseDown)
    return () => {
      container.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('mousedown', handleMouseDown)
    }
  }, [containerRef])

  if (!pos) return null

  return (
    <button
      ref={bubbleRef}
      onClick={() => { onAsk(text); setPos(null); window.getSelection()?.removeAllRanges() }}
      className="absolute z-30 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-accent text-[#06140d] text-xs font-semibold shadow-lg hover:bg-accentdk transition-colors whitespace-nowrap"
      style={{ left: pos.x, top: Math.max(8, pos.y), transform: 'translateX(-50%)' }}
    >
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.2" fill="currentColor"/>
      </svg>
      Спросить AI
    </button>
  )
}
