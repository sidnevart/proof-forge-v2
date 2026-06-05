'use client'

import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'

type Props = {
  question: string
  answer: string
  difficulty: number
  topic: string
  cardType?: string
  onRate: (rating: 1 | 2 | 3 | 4) => void
  isLoading?: boolean
}

export function FlipCard({ question, answer, difficulty, topic, cardType = 'FLASHCARD', onRate, isLoading }: Props) {
  const [flipped, setFlipped] = useState(false)
  const t = useT()

  const RATINGS = [
    { value: 1 as const, label: t('flip.unknown'), sublabel: t('flip.unknown.sub'), className: 'rating-1' },
    { value: 2 as const, label: t('flip.hard'), sublabel: t('flip.hard.sub'), className: 'rating-2' },
    { value: 4 as const, label: t('flip.easy'), sublabel: t('flip.easy.sub'), className: 'rating-3' },
  ]

  const DIFFICULTY_LABEL = ['', t('flip.diff.basic'), t('flip.diff.medium'), t('flip.diff.hard')]
  const cardTypeLabel = cardType.replaceAll('_', ' ').toLowerCase()

  useEffect(() => {
    setFlipped(false)
  }, [question])

  const handleFlip = () => {
    if (!flipped) setFlipped(true)
  }

  const handleRate = (rating: 1 | 2 | 3 | 4) => {
    onRate(rating)
    setFlipped(false)
  }

  return (
    <div className="w-full max-w-lg mx-auto select-none">
      {/* Card flip area */}
      <div
        className={`flip-container w-full cursor-pointer ${flipped ? 'flipped' : ''}`}
        style={{ height: 360 }}
        onClick={handleFlip}
        role="button"
        aria-label={flipped ? t('flip.aria.shown') : t('flip.aria.tap')}
      >
        <div className="flip-inner">
          {/* Front — question */}
          <div className="flip-face surface rounded-2xl surface-hover flex flex-col p-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-mono text-mute truncate pr-3">{topic}</span>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[10px] font-mono text-accent bg-accentsoft px-2 py-0.5 rounded-full uppercase">
                  {cardTypeLabel}
                </span>
                <span className="text-xs font-mono text-mute bg-sand px-2 py-0.5 rounded-full">
                  {DIFFICULTY_LABEL[difficulty] ?? t('flip.diff.basic')}
                </span>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto flex items-center justify-center">
              <div className="card-markdown text-center text-lg font-medium text-ink leading-relaxed w-full">
                <MarkdownRenderer>{question}</MarkdownRenderer>
              </div>
            </div>
            <div className="mt-4 text-center">
              <span className="text-xs text-mute font-mono">{t('flip.tapHint')}</span>
            </div>
          </div>

          {/* Back — answer */}
          <div className="flip-face flip-back surface rounded-2xl flex flex-col p-6 border-accent/30">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-accent">{t('flip.answerLabel')}</span>
              <span className="text-xs font-mono text-mute">{topic}</span>
            </div>
            <div className="flex-1 overflow-y-auto">
              <div className="card-markdown text-base text-ink leading-relaxed">
                <MarkdownRenderer>{answer}</MarkdownRenderer>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Rating buttons — appear after flip */}
      <div
        className={`mt-4 transition-all duration-300 ${
          flipped ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none'
        }`}
      >
        <p className="text-xs text-center text-mute font-mono mb-3">{t('flip.ratePrompt')}</p>
        <div className="grid grid-cols-3 gap-2">
          {RATINGS.map((r) => (
            <button
              key={r.value}
              className={`rating-btn ${r.className} flex flex-col items-center gap-0.5`}
              onClick={() => handleRate(r.value)}
              disabled={isLoading}
            >
              <span>{r.label}</span>
              <span className="text-[10px] opacity-70">{r.sublabel}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Hint when not flipped */}
      {!flipped && (
        <p className="mt-3 text-xs text-center text-mute/60 font-mono">
          {t('flip.thinkHint')}
        </p>
      )}
    </div>
  )
}
