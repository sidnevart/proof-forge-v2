const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'https://api.proof-forge.ru'

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('grasp_token')
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'API error')
  }
  return res.json()
}

// ── Auth ──
export const auth = {
  sendLink: (email: string, display_name?: string) =>
    req<{ message: string }>('/api/auth/send-link', {
      method: 'POST',
      body: JSON.stringify({ email, display_name }),
    }),
  verify: (token: string) =>
    req<{ access_token: string; user_id: string; email: string; display_name: string }>(
      '/api/auth/verify',
      { method: 'POST', body: JSON.stringify({ token }) }
    ),
  me: () =>
    req<{ user_id: string; email: string; display_name: string }>('/api/auth/me'),
}

// ── Cards ──
export type DueCard = {
  card_id: string
  question_id: string
  question: string
  correct_answer: string
  difficulty: number
  topic_name: string
  interval_days: number
  repetitions: number
}

export type CardStats = {
  due_today: number
  reviewed_today: number
  streak: number
  longest_streak: number
  next_due_at: string | null
}

export const cards = {
  due: (userId: string, limit = 20) =>
    req<DueCard[]>(`/api/cards/due?userId=${userId}&limit=${limit}`),
  attempt: (cardId: string, userId: string, rating: 1 | 2 | 3 | 4, user_answer?: string) =>
    req<{ card_id: string; next_review_at: string; interval_days: number; ease_factor: number }>(
      `/api/cards/${cardId}/attempt`,
      { method: 'POST', body: JSON.stringify({ user_id: userId, rating, user_answer: user_answer ?? '' }) }
    ),
  stats: (userId: string) =>
    req<CardStats>(`/api/cards/stats?userId=${userId}`),
}

// ── Mastery ──
export type MasteryProgress = {
  concepts: Array<{
    concept: string
    mastery_level: 'unknown' | 'recognize' | 'apply' | 'explain'
    theory_reps: number
    practice_reps: number
    practice_quality: number
  }>
  rollup: {
    total_concepts: number
    apply_plus: number
    apply_plus_pct: number
    total_practice_reps: number
    avg_quality: number
    blocking_expert: Array<{ concept: string; level: string }>
  }
}

export const mastery = {
  progress: (userId: string, topic?: string) =>
    req<MasteryProgress>(`/api/mastery/progress?user_id=${userId}${topic ? `&topic=${topic}` : ''}`),
  nextFocus: (userId: string, topic?: string) =>
    req<{ concept: string; mastery_level: string; reason: string }>(
      `/api/mastery/next?user_id=${userId}${topic ? `&topic=${topic}` : ''}`
    ),
}

// ── Topics ──
export type Topic = {
  id: string
  user_id: string
  name: string
  status: 'active' | 'completed'
  started_at: string
}

export const topics = {
  start: (userId: string, name: string) =>
    req<Topic>('/api/topics/start', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, name }),
    }),
}

// ── Capsules ──
export type Capsule = {
  id: string
  user_id: string
  topic_id: string
  content_md: string
  content_html: string
  summary: string
  created_at: string
  review_questions: Array<{ id: string; question: string; correct_answer: string; difficulty: number }>
}

export type CapsuleFeedback = {
  id: string
  capsule_id: string
  weak_spots: Array<{ concept: string; severity: number }>
  suggestions_md: string
  generated_at: string
  model_version: string
}

export const capsules = {
  get: (id: string) => req<Capsule>(`/api/capsules/${id}`),
  feedback: (id: string) => req<CapsuleFeedback | null>(`/api/capsules/${id}/feedback`),
  requestFeedback: (id: string) =>
    req<CapsuleFeedback>(`/api/capsules/${id}/feedback`, { method: 'POST' }),
}

// ── Agent context (topics + capsules aggregated) ──
export type AgentContext = {
  user_id: string
  topic: string | null
  profile: {
    skill_level: string
    known_topics: string[]
    weak_spots: string[]
  }
  capsules: Array<{ id: string; topic_id: string; summary: string; created_at: string }>
  weak_spots: Array<{ concept: string; severity: number }>
  recent_events: unknown[]
  generated_at: string
}

export const context = {
  get: (userId: string) =>
    req<AgentContext>(`/api/agent-context?user_id=${userId}`),
}

// ── Analytics ──
export const analytics = {
  track: (sessionId: string, eventType: string, props?: Record<string, unknown>) => {
    const body = {
      session_id: sessionId,
      event_type: eventType,
      properties: props ?? {},
      url: typeof window !== 'undefined' ? window.location.href : null,
      device: typeof window !== 'undefined'
        ? /Mobi|Android|iPhone/i.test(navigator.userAgent) ? 'mobile' : 'desktop'
        : null,
    }
    fetch(`${BASE}/api/analytics/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      keepalive: true,
    }).catch(() => {})
  },
}
