const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'https://api.proof-forge.ru'

export function sseUrl(path: string): string {
  return `${BASE}${path}`
}

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

export type TopicMaterial = {
  id: string
  topic_id: string
  user_id: string
  type: 'file' | 'link'
  name: string
  url: string | null
  content_text: string
  file_size: number | null
  created_at: string
}

export type GeneratedTopic = {
  topic_id: string
  capsule_id: string
  capsule: Capsule
}

export const topics = {
  start: (userId: string, name: string) =>
    req<Topic>('/api/topics/start', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, name }),
    }),
  get: (topicId: string) =>
    req<Topic>(`/api/topics/${topicId}`),
  list: (userId: string) =>
    req<Topic[]>(`/api/topics?user_id=${userId}`),
  getMaterials: (topicId: string) =>
    req<TopicMaterial[]>(`/api/topics/${topicId}/materials`),
  uploadFile: async (topicId: string, userId: string, file: File): Promise<TopicMaterial> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('grasp_token') : null
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/api/topics/${topicId}/materials/file?user_id=${userId}`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Upload error')
    }
    return res.json()
  },
  addLink: (topicId: string, userId: string, url: string) =>
    req<TopicMaterial>(`/api/topics/${topicId}/materials/link`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, url }),
    }),
  deleteMaterial: (topicId: string, materialId: string) =>
    req<void>(`/api/topics/${topicId}/materials/${materialId}`, { method: 'DELETE' }),
  generateCapsule: (topicId: string, userId: string) =>
    req<{ topic_id: string; capsule_id: string; status: string }>(
      `/api/topics/${topicId}/capsule/generate`,
      { method: 'POST', body: JSON.stringify({ user_id: userId }) }
    ),
  capsuleEventsUrl: (topicId: string, capsuleId: string) =>
    sseUrl(`/api/topics/${topicId}/capsule/events?capsule_id=${capsuleId}`),
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

// ── Practice Bridge ──
export type StudySession = {
  id: string
  user_id: string
  topic_id: string
  status: 'generating' | 'active' | 'paused' | 'completed' | 'error'
  conspect_md: string
  learning_goals: string[]
  created_at: string
  completed_at: string | null
}

export type PracticeTask = {
  id: string
  user_id: string
  topic_id: string
  study_session_id: string
  type: 'theory' | 'written' | 'coding' | 'debugging' | 'mini_project'
  title: string
  instructions_md: string
  target_concepts: string[]
  difficulty: number
  expected_evidence: string[]
  check_commands: string[]
  status: 'assigned' | 'opened_in_ide' | 'submitted' | 'evaluated' | 'needs_revision' | 'completed'
  created_at: string
  updated_at: string
}

export type IdeSubmission = {
  id: string
  practice_task_id: string
  user_id: string
  ide_session_id: string | null
  files: Array<{ path: string; content: string }>
  diff: string
  test_output: string
  check_command: string
  exit_code: number | null
  reflection: string
  language: string
  submitted_at: string
}

export type Evaluation = {
  id: string
  submission_id: string
  score: number
  status: 'passed' | 'needs_revision' | 'failed'
  feedback_md: string
  concept_scores: Record<string, number>
  weak_spots: Array<{ concept: string; severity: number }>
  next_action: string
  created_at: string
}

export type FollowUp = {
  id: string
  evaluation_id: string
  question: string
  expected_answer: string
  user_answer: string
  score: number | null
  feedback_md: string
}

export const practice = {
  startSession: (userId: string, topicId: string) =>
    req<{
      session: StudySession
      tasks: PracticeTask[]
      generation_status: 'generating' | 'ai' | 'fallback'
      generation_error: string | null
    }>('/api/study-sessions', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, topic_id: topicId }),
    }),
  sessionEventsUrl: (sessionId: string) => sseUrl(`/api/study-sessions/${sessionId}/events`),
  listSessions: (userId: string) =>
    req<StudySession[]>(`/api/study-sessions?user_id=${userId}`),
  getSession: (sessionId: string) =>
    req<StudySession>(`/api/study-sessions/${sessionId}`),
  listActiveTasks: (userId: string) =>
    req<PracticeTask[]>(`/api/practice-tasks?user_id=${userId}&status=active`),
  getTask: (taskId: string) =>
    req<PracticeTask>(`/api/practice-tasks/${taskId}`),
  completeSession: (sessionId: string, userId: string) =>
    req<{ session: StudySession; capsule: Capsule }>(`/api/study-sessions/${sessionId}/complete`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }),
  listFollowUps: (evaluationId: string) =>
    req<FollowUp[]>(`/api/evaluations/${evaluationId}/follow-ups`),
  answerFollowUp: (followUpId: string, userAnswer: string, score: number, feedback?: string) =>
    req<FollowUp>(`/api/follow-ups/${followUpId}/answer`, {
      method: 'POST',
      body: JSON.stringify({ user_answer: userAnswer, score, feedback_md: feedback ?? '' }),
    }),
}

// ── Chat ──
export type ChatSession = {
  id: string
  user_id: string
  topic_id: string
  study_session_id: string | null
  title: string
  status: string
  created_at: string
}

export type ChatMessage = {
  id: string
  session_id: string
  role: string
  content: string
  created_at: string
}

export const chat = {
  send: (
    userId: string,
    message: string,
    history: { role: string; content: string }[],
    topicId?: string,
  ) =>
    req<{ message: string }>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, message, history, topic_id: topicId }),
    }),
  createSession: (userId: string, topicId: string, title: string, studySessionId?: string) =>
    req<ChatSession>('/api/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, topic_id: topicId, title, study_session_id: studySessionId }),
    }),
  listSessions: (userId: string) =>
    req<ChatSession[]>(`/api/chat/sessions?user_id=${userId}`),
  getSession: (sessionId: string) =>
    req<ChatSession>(`/api/chat/sessions/${sessionId}`),
  createMessage: (sessionId: string, role: string, content: string) =>
    req<ChatMessage>(`/api/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ role, content }),
    }),
  listMessages: (sessionId: string) =>
    req<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`),
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
