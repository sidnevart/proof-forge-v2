'use client'

import { useEffect, useState } from 'react'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'https://api.proof-forge.ru'

async function fetchMetric<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}/api/metrics/${path}`)
  if (!r.ok) throw new Error(`${r.status}`)
  return r.json()
}

type Overview = {
  dau: number; dau_yesterday: number; mau: number; total_users: number
  new_users_today: number; new_users_7d: number
  capsules_generated_today: number; capsules_generated_7d: number
  cards_reviewed_today: number
  ai_cost_today_usd: number; ai_cost_7d_usd: number
  ai_total_tokens: number; ai_total_cost_usd: number
}

type Funnel = {
  period_days: number; signups: number
  created_first_topic: number; generated_first_capsule: number
  reviewed_first_card: number; still_active_7d: number
  activation_rate_pct: number; retention_7d_pct: number
}

type AiRow = {
  date: string; call_type: string; calls: number
  total_tokens: number; total_cost_usd: number; avg_latency_ms: number
}

type Engagement = {
  period_days: number; active_users: number
  total_cards_reviewed: number; avg_cards_per_active_user: number
  avg_streak: number; pct_users_with_streak: number
  avg_review_quality: number
  top_topics: Array<{ name: string; capsule_count: number }>
  session_frequency: Record<string, number>
}

type RetentionRow = { week: string; cohort_size: number; w1?: number; w2?: number; w3?: number; w4?: number }

export default function AdminPage() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [funnel, setFunnel] = useState<Funnel | null>(null)
  const [ai, setAi] = useState<AiRow[]>([])
  const [engagement, setEngagement] = useState<Engagement | null>(null)
  const [retention, setRetention] = useState<RetentionRow[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetchMetric<Overview>('overview'),
      fetchMetric<Funnel>('funnel?days=30'),
      fetchMetric<AiRow[]>('ai?days=7'),
      fetchMetric<Engagement>('engagement?days=30'),
      fetchMetric<RetentionRow[]>('retention?weeks=6'),
    ]).then(([ov, fn, aiData, eng, ret]) => {
      setOverview(ov)
      setFunnel(fn)
      setAi(aiData)
      setEngagement(eng)
      setRetention(ret)
    }).catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="max-w-5xl mx-auto px-5 py-12 text-center">
      <div className="w-8 h-8 rounded-full border-2 border-line border-t-accent animate-spin mx-auto" />
      <p className="text-mute text-sm mt-4">Loading metrics...</p>
    </div>
  )

  if (error) return (
    <div className="max-w-5xl mx-auto px-5 py-12 text-center">
      <p className="text-danger text-sm">Failed to load metrics: {error}</p>
    </div>
  )

  const dau_delta = overview ? overview.dau - overview.dau_yesterday : 0

  return (
    <div className="max-w-5xl mx-auto px-5 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 text-xs font-mono text-accent bg-accentsoft border border-accent/20 rounded-full px-3 py-1 mb-3">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          Internal Dashboard
        </div>
        <h1 className="font-display text-3xl font-bold text-ink">Grasp Metrics</h1>
        <p className="text-mute text-sm mt-1">Real-time business data</p>
      </div>

      {/* Overview grid */}
      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          <MetricCard label="DAU" value={overview.dau} delta={dau_delta} unit="users" />
          <MetricCard label="MAU" value={overview.mau} unit="users" />
          <MetricCard label="Total Users" value={overview.total_users} />
          <MetricCard label="New (7d)" value={overview.new_users_7d} unit="users" accent />
          <MetricCard label="Capsules today" value={overview.capsules_generated_today} />
          <MetricCard label="Capsules 7d" value={overview.capsules_generated_7d} />
          <MetricCard label="Cards today" value={overview.cards_reviewed_today} unit="cards" />
          <MetricCard label="AI cost 7d" value={`$${overview.ai_cost_7d_usd.toFixed(4)}`} sub={`Total: $${overview.ai_total_cost_usd.toFixed(3)}`} />
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6 mb-6">
        {/* Activation Funnel */}
        {funnel && (
          <div className="surface rounded-2xl p-5">
            <h2 className="font-semibold text-ink mb-1">Activation Funnel</h2>
            <p className="text-xs text-mute font-mono mb-4">Last {funnel.period_days} days</p>
            <FunnelBar label="Signups" value={funnel.signups} max={funnel.signups} />
            <FunnelBar label="Created topic" value={funnel.created_first_topic} max={funnel.signups} />
            <FunnelBar label="Generated capsule" value={funnel.generated_first_capsule} max={funnel.signups} accent />
            <FunnelBar label="Reviewed cards" value={funnel.reviewed_first_card} max={funnel.signups} />
            <div className="mt-4 pt-4 border-t border-line flex gap-4 text-xs font-mono">
              <span className="text-mute">Activation: <span className="text-accent">{funnel.activation_rate_pct}%</span></span>
              <span className="text-mute">D7 retention: <span className="text-ink">{funnel.retention_7d_pct}%</span></span>
            </div>
          </div>
        )}

        {/* Engagement */}
        {engagement && (
          <div className="surface rounded-2xl p-5">
            <h2 className="font-semibold text-ink mb-1">Engagement</h2>
            <p className="text-xs text-mute font-mono mb-4">Last {engagement.period_days} days</p>
            <div className="space-y-2.5">
              <EngRow label="Active users" value={engagement.active_users} />
              <EngRow label="Cards reviewed" value={engagement.total_cards_reviewed} />
              <EngRow label="Avg cards/user" value={engagement.avg_cards_per_active_user} />
              <EngRow label="Avg streak" value={`${engagement.avg_streak} days`} />
              <EngRow label="Users w/ streak" value={`${engagement.pct_users_with_streak}%`} accent />
              <EngRow label="Avg quality" value={`${(engagement.avg_review_quality * 100).toFixed(0)}%`} />
            </div>
            {engagement.top_topics.length > 0 && (
              <div className="mt-4 pt-4 border-t border-line">
                <p className="text-xs font-mono text-mute mb-2">Top topics</p>
                {engagement.top_topics.map((t) => (
                  <div key={t.name} className="flex items-center justify-between py-1">
                    <span className="text-xs text-ink truncate flex-1">{t.name}</span>
                    <span className="text-xs font-mono text-mute ml-2">{t.capsule_count} capsules</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* AI Usage Table */}
      {ai.length > 0 && (
        <div className="surface rounded-2xl p-5 mb-6">
          <h2 className="font-semibold text-ink mb-1">AI Usage</h2>
          <p className="text-xs text-mute font-mono mb-4">Last 7 days by call type</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs font-mono text-mute border-b border-line">
                  <th className="text-left pb-2">Date</th>
                  <th className="text-left pb-2">Type</th>
                  <th className="text-right pb-2">Calls</th>
                  <th className="text-right pb-2">Tokens</th>
                  <th className="text-right pb-2">Cost</th>
                  <th className="text-right pb-2">Latency</th>
                </tr>
              </thead>
              <tbody>
                {ai.map((r, i) => (
                  <tr key={i} className="border-b border-line/50 hover:bg-card/40">
                    <td className="py-2 font-mono text-xs text-mute">{r.date}</td>
                    <td className="py-2">
                      <span className={`text-xs font-mono px-2 py-0.5 rounded-full ${
                        r.call_type === 'capsule_gen' ? 'bg-accentsoft text-accent' :
                        r.call_type === 'feedback' ? 'bg-info/10 text-info' :
                        'bg-card text-mute'
                      }`}>{r.call_type}</span>
                    </td>
                    <td className="py-2 text-right font-mono text-sm">{r.calls}</td>
                    <td className="py-2 text-right font-mono text-sm">{r.total_tokens.toLocaleString()}</td>
                    <td className="py-2 text-right font-mono text-sm text-accent">${r.total_cost_usd.toFixed(5)}</td>
                    <td className="py-2 text-right font-mono text-xs text-mute">{r.avg_latency_ms}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Retention */}
      {retention.filter(r => r.cohort_size > 0).length > 0 && (
        <div className="surface rounded-2xl p-5">
          <h2 className="font-semibold text-ink mb-1">Cohort Retention</h2>
          <p className="text-xs text-mute font-mono mb-4">Weekly cohorts — % still active</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs font-mono text-mute border-b border-line">
                  <th className="text-left pb-2">Week</th>
                  <th className="text-right pb-2">Size</th>
                  <th className="text-right pb-2">W1</th>
                  <th className="text-right pb-2">W2</th>
                  <th className="text-right pb-2">W3</th>
                </tr>
              </thead>
              <tbody>
                {retention.filter(r => r.cohort_size > 0).map((r) => (
                  <tr key={r.week} className="border-b border-line/50">
                    <td className="py-2 font-mono text-xs text-mute">{r.week}</td>
                    <td className="py-2 text-right font-mono text-sm">{r.cohort_size}</td>
                    <RetentionCell value={r.w1} total={r.cohort_size} />
                    <RetentionCell value={r.w2} total={r.cohort_size} />
                    <RetentionCell value={r.w3} total={r.cohort_size} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-center text-xs text-mute font-mono mt-8">
        /admin — internal only · <a href="/api/metrics/overview" className="text-accent" target="_blank">raw JSON</a>
      </p>
    </div>
  )
}

// ── Metric card ───────────────────────────────────────────────────────────────
function MetricCard({ label, value, delta, unit, sub, accent }: {
  label: string; value: number | string; delta?: number; unit?: string; sub?: string; accent?: boolean
}) {
  return (
    <div className="surface rounded-2xl p-4">
      <div className="text-xs font-mono text-mute mb-1">{label}</div>
      <div className={`text-2xl font-mono font-bold ${accent ? 'text-accent' : 'text-ink'}`}>
        {value}
      </div>
      {unit && <div className="text-xs text-mute">{unit}</div>}
      {delta !== undefined && delta !== 0 && (
        <div className={`text-xs font-mono mt-0.5 ${delta > 0 ? 'text-accent' : 'text-danger'}`}>
          {delta > 0 ? '+' : ''}{delta} vs yesterday
        </div>
      )}
      {sub && <div className="text-xs text-mute mt-0.5">{sub}</div>}
    </div>
  )
}

// ── Funnel bar ────────────────────────────────────────────────────────────────
function FunnelBar({ label, value, max, accent }: { label: string; value: number; max: number; accent?: boolean }) {
  const pct = max > 0 ? Math.round(value / max * 100) : 0
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-ink">{label}</span>
        <span className="text-sm font-mono text-mute">{value} <span className="text-xs">({pct}%)</span></span>
      </div>
      <div className="h-1.5 bg-sand rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${accent ? 'bg-accent' : 'bg-accent/50'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// ── Engagement row ────────────────────────────────────────────────────────────
function EngRow({ label, value, accent }: { label: string; value: number | string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-mute">{label}</span>
      <span className={`text-sm font-mono font-medium ${accent ? 'text-accent' : 'text-ink'}`}>{value}</span>
    </div>
  )
}

// ── Retention cell ────────────────────────────────────────────────────────────
function RetentionCell({ value, total }: { value?: number; total: number }) {
  if (value === undefined) return <td className="py-2 text-right text-mute/30">—</td>
  const pct = total > 0 ? Math.round(value / total * 100) : 0
  const color = pct >= 40 ? 'text-accent' : pct >= 20 ? 'text-warn' : 'text-danger'
  return (
    <td className={`py-2 text-right font-mono text-sm ${color}`}>
      {pct}%
    </td>
  )
}
