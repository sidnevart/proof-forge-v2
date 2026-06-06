'use client'

import { useEffect, useRef, useState } from 'react'
import { onboarding, type OnboardingSlot, type StudyProfile } from '@/lib/api'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { useT } from '@/lib/i18n'

type Phase = 'loading' | 'asking' | 'planning' | 'plan' | 'error'

interface Props {
  userId: string
  topicId: string
  /** Called with the resolved profile when the user confirms ("Поехали"). */
  onConfirm: (profile: StudyProfile) => void
  /** Called when the user skips the interview ("Пропустить") → balanced default. */
  onSkip: () => void
}

/**
 * Chat-styled pre-topic interview. Walks the AI-built slots one at a time (chips +
 * free text), then shows a plan bubble with Поехали / Поправить. Answers live in
 * client state and are sent in one batch to /onboarding/plan. The whole flow degrades
 * gracefully — if questions can't load, it falls back to skip.
 */
export function OnboardingChat({ userId, topicId, onConfirm, onSkip }: Props) {
  const t = useT()
  const [phase, setPhase] = useState<Phase>('loading')
  const [slots, setSlots] = useState<OnboardingSlot[]>([])
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string[]>>({})
  const [freeText, setFreeText] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [planMd, setPlanMd] = useState('')
  const [profile, setProfile] = useState<StudyProfile | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    onboarding.questions(userId, topicId)
      .then((res) => {
        if (cancelled) return
        setSlots(res.slots)
        setPhase(res.slots.length ? 'asking' : 'plan')
      })
      .catch(() => { if (!cancelled) setPhase('error') })
    return () => { cancelled = true }
  }, [userId, topicId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [step, phase, planMd])

  const slot = slots[step]

  const toggleChip = (value: string) => {
    if (!slot) return
    if (slot.multiselect) {
      setSelected((prev) => prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value])
    } else {
      setSelected([value])
    }
  }

  const commitAnswer = () => {
    if (!slot) return
    const values = [...selected]
    const free = freeText.trim()
    if (free) values.push(free)
    const nextAnswers = { ...answers, [slot.id]: values }
    setAnswers(nextAnswers)
    setSelected([])
    setFreeText('')
    if (step + 1 < slots.length) {
      setStep(step + 1)
    } else {
      requestPlan(nextAnswers)
    }
  }

  const requestPlan = async (finalAnswers: Record<string, string[]>) => {
    setPhase('planning')
    try {
      const res = await onboarding.plan(userId, topicId, finalAnswers)
      setPlanMd(res.plan_md)
      setProfile(res.study_profile)
      setPhase('plan')
    } catch {
      setPhase('error')
    }
  }

  const editPlan = () => {
    setPhase('asking')
    setStep(0)
  }

  if (phase === 'loading') {
    return (
      <div className="flex items-center gap-2 py-8 justify-center">
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        <span className="text-xs text-mute font-mono">{t('onboarding.preparing')}</span>
      </div>
    )
  }

  if (phase === 'error') {
    // Never block learning — offer to proceed with the balanced default.
    return (
      <div className="text-center py-8">
        <p className="text-sm text-mute mb-4">{t('onboarding.error')}</p>
        <button onClick={onSkip} className="px-4 py-2.5 rounded-xl bg-accent text-[#06140d] text-sm font-semibold hover:bg-accentdk transition-colors">
          {t('onboarding.startAnyway')}
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Answered slots as a transcript */}
      {slots.slice(0, step).map((s) => (
        <div key={s.id} className="space-y-1.5">
          <MentorBubble>{s.question}</MentorBubble>
          {answers[s.id]?.length > 0 && (
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-card border border-line px-3.5 py-2 text-sm text-ink">
                {answers[s.id].join(', ')}
              </div>
            </div>
          )}
        </div>
      ))}

      {/* Active slot */}
      {phase === 'asking' && slot && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-mute uppercase tracking-wider">
              {step + 1}/{slots.length}
            </span>
            <button onClick={onSkip} className="text-xs text-mute hover:text-ink transition-colors font-mono">
              {t('onboarding.skip')} →
            </button>
          </div>
          <MentorBubble>{slot.question}</MentorBubble>
          <div className="flex flex-wrap gap-1.5">
            {slot.options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => toggleChip(opt.value)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  selected.includes(opt.value)
                    ? 'bg-accent text-[#06140d] border-accent'
                    : 'bg-card text-mute border-line hover:text-ink hover:border-accent/40'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {slot.allow_free_text && (
            <input
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') commitAnswer() }}
              placeholder={t('onboarding.freeText')}
              className="w-full px-3 py-2 rounded-xl border border-line bg-card text-ink text-sm placeholder:text-mute/50 focus:outline-none focus:border-accent/60 transition-colors"
            />
          )}
          <button
            onClick={commitAnswer}
            disabled={selected.length === 0 && !freeText.trim()}
            className="w-full py-2.5 rounded-xl bg-accent text-[#06140d] text-sm font-semibold hover:bg-accentdk transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {step + 1 < slots.length ? t('onboarding.next') : t('onboarding.done')}
          </button>
        </div>
      )}

      {/* Plan synthesis */}
      {phase === 'planning' && (
        <div className="flex items-center gap-2 py-4 justify-center">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          <span className="text-xs text-mute font-mono">{t('onboarding.planning')}</span>
        </div>
      )}

      {/* Plan bubble + confirm */}
      {phase === 'plan' && (
        <div className="space-y-3">
          <MentorBubble>
            {planMd ? <div className="prose-grasp text-sm"><MarkdownRenderer>{planMd}</MarkdownRenderer></div> : t('onboarding.planFallback')}
          </MentorBubble>
          <div className="flex gap-2">
            <button
              onClick={() => onConfirm(profile as StudyProfile)}
              className="flex-1 py-3 rounded-xl bg-accent text-[#06140d] font-semibold text-sm hover:bg-accentdk transition-colors"
            >
              {t('onboarding.go')} →
            </button>
            <button
              onClick={editPlan}
              className="px-4 py-3 rounded-xl border border-line text-ink text-sm font-medium hover:border-accent/40 transition-colors"
            >
              {t('onboarding.edit')}
            </button>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}

function MentorBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-start">
      <div className="w-6 h-6 rounded-md bg-accentsoft border border-accent/20 flex items-center justify-center shrink-0 mr-2 mt-1">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
          <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))" />
        </svg>
      </div>
      <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-sand/40 border border-line/60 px-3.5 py-2.5 text-sm text-ink">
        {children}
      </div>
    </div>
  )
}
