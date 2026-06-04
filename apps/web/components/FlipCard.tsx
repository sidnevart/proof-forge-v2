'use client'

import { useState } from 'react'

type Props = {
  question: string
  answer: string
  difficulty: number
  topic: string
  onRate: (rating: 1 | 2 | 3 | 4) => void
  isLoading?: boolean
}

const RATINGS = [
  { value: 1 as const, label: 'Снова', sublabel: '<1 дня', className: 'rating-1' },
  { value: 2 as const, label: 'Сложно', sublabel: '+25%', className: 'rating-2' },
  { value: 3 as const, label: 'Хорошо', sublabel: '×2.5', className: 'rating-3' },
  { value: 4 as const, label: 'Легко', sublabel: '×3.5', className: 'rating-4' },
]

const DIFFICULTY_LABEL = ['', 'Базовый', 'Средний', 'Сложный']

export function FlipCard({ question, answer, difficulty, topic, onRate, isLoading }: Props) {
  const [flipped, setFlipped] = useState(false)

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
        style={{ height: 260 }}
        onClick={handleFlip}
        role="button"
        aria-label={flipped ? 'Показан ответ' : 'Нажми чтобы увидеть ответ'}
      >
        <div className="flip-inner">
          {/* Front — question */}
          <div className="flip-face surface rounded-2xl surface-hover flex flex-col p-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-mono text-mute">{topic}</span>
              <span className="text-xs font-mono text-mute bg-sand px-2 py-0.5 rounded-full">
                {DIFFICULTY_LABEL[difficulty] ?? 'Базовый'}
              </span>
            </div>
            <div className="flex-1 flex items-center justify-center">
              <p className="text-lg font-medium text-ink leading-relaxed text-center">{question}</p>
            </div>
            <div className="mt-4 text-center">
              <span className="text-xs text-mute font-mono">нажми чтобы увидеть ответ →</span>
            </div>
          </div>

          {/* Back — answer */}
          <div className="flip-face flip-back surface rounded-2xl flex flex-col p-6 border-accent/30">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-accent">ответ</span>
              <span className="text-xs font-mono text-mute">{topic}</span>
            </div>
            <div className="flex-1 overflow-y-auto">
              <p className="text-base text-ink leading-relaxed">{answer}</p>
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
        <p className="text-xs text-center text-mute font-mono mb-3">Насколько хорошо ответил?</p>
        <div className="flex gap-2">
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
          Подумай перед тем как смотреть ответ
        </p>
      )}
    </div>
  )
}
