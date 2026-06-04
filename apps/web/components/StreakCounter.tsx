'use client'

export function StreakCounter({ streak, size = 'md' }: { streak: number; size?: 'sm' | 'md' | 'lg' }) {
  const isActive = streak > 0
  const textSize = size === 'sm' ? 'text-xl' : size === 'lg' ? 'text-5xl' : 'text-3xl'
  const labelSize = size === 'sm' ? 'text-xs' : 'text-sm'

  return (
    <div className="flex flex-col items-center gap-1">
      <div className={`font-mono font-bold ${textSize} ${isActive ? 'text-accent' : 'text-mute'}`}>
        {streak}
      </div>
      <div className={`${labelSize} text-mute font-medium flex items-center gap-1`}>
        <span>{isActive ? '🔥' : '💤'}</span>
        <span>{streak === 1 ? 'день' : streak >= 2 && streak <= 4 ? 'дня' : 'дней'}</span>
      </div>
    </div>
  )
}

export function StreakBar({ streak, target = 7 }: { streak: number; target?: number }) {
  const pct = Math.min(100, (streak / target) * 100)
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs text-mute font-mono">
        <span>🔥 {streak} дней подряд</span>
        <span>цель: {target}</span>
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
