'use client'

import { useT, useLocale, ruPlural } from '@/lib/i18n'

export function StreakCounter({ streak, size = 'md' }: { streak: number; size?: 'sm' | 'md' | 'lg' }) {
  const isActive = streak > 0
  const textSize = size === 'sm' ? 'text-xl' : size === 'lg' ? 'text-5xl' : 'text-3xl'
  const labelSize = size === 'sm' ? 'text-xs' : 'text-sm'
  const t = useT()
  const { locale } = useLocale()

  const dayWord = locale === 'ru'
    ? ruPlural(streak, ['день', 'дня', 'дней'])
    : streak === 1 ? t('streak.day') : t('streak.days')

  return (
    <div className="flex flex-col items-center gap-1">
      <div className={`font-mono font-bold ${textSize} ${isActive ? 'text-accent' : 'text-mute'}`}>
        {streak}
      </div>
      <div className={`${labelSize} text-mute font-medium flex items-center gap-1`}>
        <span>{isActive ? '🔥' : '💤'}</span>
        <span>{dayWord}</span>
      </div>
    </div>
  )
}

export function StreakBar({ streak, target = 7 }: { streak: number; target?: number }) {
  const pct = Math.min(100, (streak / target) * 100)
  const t = useT()
  const { locale } = useLocale()

  const streakLabel = locale === 'ru'
    ? `🔥 ${streak} ${ruPlural(streak, ['день', 'дня', 'дней'])} ${t('streak.inARow')}`
    : `🔥 ${streak} ${streak === 1 ? t('streak.day') : t('streak.days')} ${t('streak.inARow')}`

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs text-mute font-mono">
        <span>{streakLabel}</span>
        <span>{t('streak.goal')}: {target}</span>
      </div>
      <div className="h-1.5 rounded-full bg-sand overflow-hidden">
        <div
          className="h-full rounded-full bg-accent prog-fill"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
