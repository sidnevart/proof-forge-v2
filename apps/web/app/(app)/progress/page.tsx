'use client'

import { useEffect, useState } from 'react'
import { getStoredUser } from '@/lib/auth'
import { mastery, cards, type MasteryProgress, type CardStats } from '@/lib/api'
import { MasteryBadge } from '@/components/MasteryBadge'
import { StreakCounter } from '@/components/StreakCounter'
import { Skeleton } from '@/components/ui/Skeleton'
import { useT } from '@/lib/i18n'

type Level = 'unknown' | 'recognize' | 'apply' | 'explain'

const LEVEL_ORDER: Level[] = ['unknown', 'recognize', 'apply', 'explain']

export default function ProgressPage() {
  const user = getStoredUser()
  const [progress, setProgress] = useState<MasteryProgress | null>(null)
  const [stats, setStats] = useState<CardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<Level | 'all'>('all')
  const t = useT()

  const LEVEL_LABEL: Record<Level, string> = {
    unknown: t('progress.level.unknown'),
    recognize: t('progress.level.recognize'),
    apply: t('progress.level.apply'),
    explain: t('progress.level.explain'),
  }

  const LEVEL_DESC: Record<Level, string> = {
    unknown: t('progress.desc.unknown'),
    recognize: t('progress.desc.recognize'),
    apply: t('progress.desc.apply'),
    explain: t('progress.desc.explain'),
  }

  useEffect(() => {
    if (!user) return
    Promise.all([
      mastery.progress(user.user_id),
      cards.stats(user.user_id),
    ]).then(([p, s]) => {
      setProgress(p)
      setStats(s)
    }).catch(console.error).finally(() => setLoading(false))
  }, [user?.user_id])

  const filtered = progress?.concepts.filter(
    (c) => filter === 'all' || c.mastery_level === filter
  ) ?? []

  const rollup = progress?.rollup

  return (
    <div className="max-w-2xl mx-auto px-5 py-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <p className="text-xs font-mono text-accent mb-1">{t('progress.breadcrumb')}</p>
          <h1 className="font-display text-3xl font-bold text-ink">{t('progress.title')}</h1>
        </div>
        {stats && <StreakCounter streak={stats.streak} />}
      </div>

      {/* Rollup stats */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          {[0,1,2,3].map(i => <Skeleton key={i} className="h-20" />)}
        </div>
      ) : rollup && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          <RollupCard label={t('progress.rollup.concepts')} value={rollup.total_concepts} />
          <RollupCard label={t('progress.rollup.applyPlus')} value={rollup.apply_plus} accent />
          <RollupCard label={t('progress.rollup.quality')} value={`${Math.round(rollup.avg_quality * 100)}%`} />
          <RollupCard label={t('progress.rollup.reps')} value={rollup.total_practice_reps} />
        </div>
      )}

      {/* Progress bar */}
      {!loading && rollup && rollup.total_concepts > 0 && (
        <div className="surface rounded-2xl p-5 mb-6">
          <div className="flex justify-between text-xs font-mono text-mute mb-2">
            <span>{t('progress.bar.label')}</span>
            <span>{rollup.apply_plus_pct.toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-sand rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full prog-fill"
              style={{ width: `${rollup.apply_plus_pct}%` }}
            />
          </div>
          <div className="mt-3 flex gap-3">
            {LEVEL_ORDER.map((level) => {
              const count = progress!.concepts.filter(c => c.mastery_level === level).length
              if (count === 0) return null
              return (
                <div key={level} className="flex items-center gap-1.5">
                  <MasteryBadge level={level} size="sm" />
                  <span className="text-xs text-mute font-mono">{count}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Blocking expert */}
      {!loading && (rollup?.blocking_expert?.length ?? 0) > 0 && (
        <div className="surface rounded-2xl p-5 mb-6 border-warn/30">
          <div className="text-xs font-mono text-warn mb-3">{t('progress.blocking')}</div>
          <div className="flex flex-wrap gap-2">
            {rollup!.blocking_expert.map(({ concept, level }) => (
              <MasteryBadge key={concept} level={level as Level} concept={concept} />
            ))}
          </div>
        </div>
      )}

      {/* Filter */}
      {!loading && (progress?.concepts.length ?? 0) > 0 && (
        <div className="flex flex-wrap gap-2 mb-5">
          <FilterChip label={t('progress.filter.all')} active={filter === 'all'} onClick={() => setFilter('all')} />
          {LEVEL_ORDER.map((level) => {
            const count = progress!.concepts.filter(c => c.mastery_level === level).length
            if (count === 0) return null
            return (
              <FilterChip
                key={level}
                label={`${LEVEL_LABEL[level]} (${count})`}
                active={filter === level}
                onClick={() => setFilter(level)}
              />
            )
          })}
        </div>
      )}

      {/* Concept grid */}
      {loading ? (
        <div className="space-y-2">
          {[0,1,2,3,4].map(i => <Skeleton key={i} className="h-16" />)}
        </div>
      ) : filtered.length > 0 ? (
        <div className="space-y-2">
          {filtered.map((concept) => (
            <ConceptRow key={concept.concept} concept={concept} t={t} />
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <p className="text-mute text-sm">
            {filter === 'all'
              ? t('progress.empty.all')
              : `${t('progress.empty.filteredPrefix')} "${LEVEL_LABEL[filter as Level]}"`}
          </p>
        </div>
      )}

      {/* Legend */}
      {!loading && (progress?.concepts.length ?? 0) > 0 && (
        <div className="mt-10 surface rounded-2xl p-5">
          <div className="text-xs font-mono text-mute mb-4">{t('progress.legend.title')}</div>
          <div className="space-y-3">
            {LEVEL_ORDER.map((level) => (
              <div key={level} className="flex items-center gap-3">
                <MasteryBadge level={level} size="sm" />
                <span className="text-xs text-mute">{LEVEL_DESC[level]}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ConceptRow({ concept, t }: { concept: MasteryProgress['concepts'][0]; t: (k: string) => string }) {
  const quality = Math.round(concept.practice_quality * 100)
  return (
    <div className="surface surface-hover rounded-xl p-4 flex items-center gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-ink truncate">{concept.concept}</span>
          <MasteryBadge level={concept.mastery_level as 'unknown' | 'recognize' | 'apply' | 'explain'} size="sm" />
        </div>
        <div className="flex items-center gap-3 text-xs font-mono text-mute">
          <span>{t('progress.concept.theory')}: {concept.theory_reps}</span>
          <span>{t('progress.concept.practice')}: {concept.practice_reps}</span>
          {concept.practice_reps > 0 && <span>{t('progress.concept.quality')}: {quality}%</span>}
        </div>
      </div>
      {/* Mini quality bar */}
      {concept.practice_reps > 0 && (
        <div className="w-16 h-1.5 bg-sand rounded-full overflow-hidden shrink-0">
          <div
            className="h-full rounded-full prog-fill"
            style={{
              width: `${quality}%`,
              background: quality >= 80 ? 'rgb(var(--accent))' : quality >= 60 ? '#f5c542' : 'rgb(var(--danger))',
            }}
          />
        </div>
      )}
    </div>
  )
}

function RollupCard({ label, value, accent }: { label: string; value: number | string; accent?: boolean }) {
  return (
    <div className="surface rounded-xl p-4">
      <div className="text-xs font-mono text-mute mb-1">{label}</div>
      <div className={`text-2xl font-mono font-bold ${accent ? 'text-accent' : 'text-ink'}`}>{value}</div>
    </div>
  )
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
        active
          ? 'bg-accentsoft border-accent/30 text-accent'
          : 'surface text-mute hover:text-ink'
      }`}
    >
      {label}
    </button>
  )
}
