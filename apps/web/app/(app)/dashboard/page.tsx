'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { getStoredUser } from '@/lib/auth'
import { cards, mastery, context, type CardStats, type AgentContext } from '@/lib/api'
import { MasteryBadge } from '@/components/MasteryBadge'
import { StreakBar } from '@/components/StreakCounter'
import { Skeleton } from '@/components/ui/Skeleton'

export default function DashboardPage() {
  const user = getStoredUser()
  const [stats, setStats] = useState<CardStats | null>(null)
  const [ctx, setCtx] = useState<AgentContext | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) return
    Promise.all([
      cards.stats(user.user_id),
      context.get(user.user_id),
    ]).then(([s, c]) => {
      setStats(s)
      setCtx(c)
    }).catch(console.error).finally(() => setLoading(false))
  }, [user?.user_id])

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Доброе утро' : hour < 18 ? 'Добрый день' : 'Добрый вечер'

  return (
    <div className="max-w-3xl mx-auto px-5 py-8">
      {/* Header */}
      <div className="mb-8">
        <p className="text-sm text-mute font-mono mb-1">{greeting}</p>
        <h1 className="font-display text-3xl font-bold text-ink">
          {user?.display_name || 'Привет'} <span className="text-mute">👋</span>
        </h1>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-8">
        <StatCard
          label="К повторению"
          value={loading ? null : stats?.due_today ?? 0}
          unit="карточек"
          accent={!loading && (stats?.due_today ?? 0) > 0}
          href="/cards"
        />
        <StatCard
          label="Сегодня"
          value={loading ? null : stats?.reviewed_today ?? 0}
          unit="повторено"
        />
        <StatCard
          label="Тем изучено"
          value={loading ? null : ctx?.profile?.known_topics?.length ?? 0}
          unit="тем"
          className="col-span-2 sm:col-span-1"
        />
      </div>

      {/* Streak */}
      {!loading && stats && (
        <div className="surface surface-hover rounded-2xl p-5 mb-6">
          <StreakBar streak={stats.streak} target={7} />
        </div>
      )}
      {loading && <Skeleton className="h-16 mb-6" />}

      {/* CTA — due cards */}
      {!loading && (stats?.due_today ?? 0) > 0 && (
        <Link
          href="/cards"
          className="flex items-center justify-between w-full surface surface-hover rounded-2xl p-5 mb-6 group"
        >
          <div>
            <div className="text-sm font-mono text-accent mb-0.5">Пора повторить</div>
            <div className="text-lg font-semibold text-ink">
              {stats!.due_today} {pluralCards(stats!.due_today)} ждут тебя
            </div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-accentsoft flex items-center justify-center text-accent group-hover:bg-accent group-hover:text-[#06140d] transition-all">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </div>
        </Link>
      )}

      {/* Weak spots */}
      {!loading && (ctx?.weak_spots?.length ?? 0) > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-mono text-mute mb-3">Слабые места — подтянуть</h2>
          <div className="flex flex-wrap gap-2">
            {ctx!.weak_spots.slice(0, 6).map((ws) => (
              <div
                key={ws.concept}
                className="flex items-center gap-2 surface rounded-xl px-3 py-2"
              >
                <div
                  className="w-1.5 h-1.5 rounded-full bg-danger"
                  style={{ opacity: Math.min(1, ws.severity / 3) }}
                />
                <span className="text-sm text-ink">{ws.concept}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent capsules */}
      {!loading && (ctx?.capsules?.length ?? 0) > 0 && (
        <div>
          <h2 className="text-sm font-mono text-mute mb-3">Последние капсулы</h2>
          <div className="space-y-2">
            {ctx!.capsules.slice(0, 4).map((c) => (
              <Link
                key={c.id}
                href={`/capsule/${c.id}`}
                className="flex items-start gap-3 surface surface-hover rounded-xl p-4 group"
              >
                <div className="w-8 h-8 rounded-lg bg-accentsoft flex items-center justify-center text-accent shrink-0 mt-0.5">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-ink line-clamp-2">{c.summary}</p>
                  <p className="text-xs text-mute mt-1 font-mono">
                    {new Date(c.created_at).toLocaleDateString('ru', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-mute shrink-0 group-hover:text-accent transition-colors mt-1">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !ctx?.capsules?.length && (
        <div className="space-y-3">
          {/* Primary CTA */}
          <Link
            href="/topics/new"
            className="flex items-start gap-4 w-full surface surface-hover rounded-2xl p-6 group border border-accent/20 bg-accentsoft/30"
          >
            <div className="w-12 h-12 rounded-xl bg-accentsoft border border-accent/30 flex items-center justify-center text-accent shrink-0">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>
              </svg>
            </div>
            <div className="flex-1 text-left">
              <div className="text-xs font-mono text-accent mb-1">Начать здесь</div>
              <div className="font-semibold text-ink">Начать изучение темы</div>
              <div className="text-sm text-mute mt-0.5">
                Загрузи файлы или ссылки — платформа создаст капсулу и карточки
              </div>
            </div>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-accent shrink-0 mt-1 group-hover:translate-x-0.5 transition-transform">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </Link>

          {/* Secondary — Claude plugin */}
          <div className="surface rounded-2xl p-5">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-card border border-line flex items-center justify-center shrink-0 mt-0.5">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--mute))" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-5"/></svg>
              </div>
              <div>
                <div className="font-medium text-ink text-sm">Используешь Claude Desktop?</div>
                <div className="text-sm text-mute mt-0.5">
                  Установи Grasp-плагин — учись прямо в Claude с доступом к кодовой базе и YouTube.
                </div>
                <a
                  href="https://github.com/sidnevart/proof-forge-v2"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-accent hover:text-accentdk transition-colors mt-2 font-mono"
                >
                  Установить плагин →
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Link to start new topic when user already has content */}
      {!loading && (ctx?.capsules?.length ?? 0) > 0 && (
        <div className="mt-8 pt-6 border-t border-line">
          <Link
            href="/topics/new"
            className="flex items-center gap-2 text-sm text-mute hover:text-accent transition-colors font-mono"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Начать изучение новой темы
          </Link>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, unit, accent, href, className = '' }: {
  label: string; value: number | null; unit: string; accent?: boolean; href?: string; className?: string
}) {
  const content = (
    <div className={`surface surface-hover rounded-2xl p-4 ${accent ? 'border-accent/40' : ''} ${className}`}>
      <div className="text-xs font-mono text-mute mb-1">{label}</div>
      {value === null
        ? <Skeleton className="h-8 w-16 mt-1" />
        : <div className={`text-3xl font-mono font-bold ${accent ? 'text-accent' : 'text-ink'}`}>{value}</div>
      }
      <div className="text-xs text-mute mt-0.5">{unit}</div>
    </div>
  )
  if (href) return <Link href={href}>{content}</Link>
  return content
}

function pluralCards(n: number) {
  if (n % 10 === 1 && n % 100 !== 11) return 'карточка'
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return 'карточки'
  return 'карточек'
}
