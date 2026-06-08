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
  // 204 No Content (e.g. DELETE) and other empty bodies have no JSON to parse —
  // calling res.json() on them throws "Unexpected end of JSON input", which made
  // a successful DELETE reject and the caller's catch swallow it (the folder was
  // deleted on the server but the UI never updated, then a retry hit a real 404).
  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
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

// ── API Keys (IDE plugins) ──
export type ApiKeyOut = { id: string; name: string; created_at: string; last_used_at: string | null }
export type ApiKeyCreateResponse = ApiKeyOut & { raw_key: string }

export const apiKeys = {
  create: (name?: string) =>
    req<ApiKeyCreateResponse>('/api/auth/api-keys', {
      method: 'POST',
      body: JSON.stringify({ name: name || '' }),
    }),
  list: () => req<ApiKeyOut[]>('/api/auth/api-keys'),
  revoke: (keyId: string) =>
    req<void>(`/api/auth/api-keys/${keyId}`, { method: 'DELETE' }),
}

// ── Cards ──
export type DueCard = {
  source: 'capsule' | 'topic'
  card_type: 'FLASHCARD' | 'FILL_BLANK' | 'CODE_REVIEW' | 'PRACTICAL' | string
  card_id: string
  question_id: string | null
  question: string
  correct_answer: string
  difficulty: number
  topic_id: string
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

export type TopicDue = {
  topic_id: string
  topic_name: string
  due_count: number
}

export const cards = {
  due: (userId: string, limit = 20, topicId?: string) =>
    req<DueCard[]>(
      `/api/cards/due?userId=${userId}&limit=${limit}${topicId ? `&topicId=${topicId}` : ''}`,
    ),
  topicsWithDue: (userId: string) =>
    req<TopicDue[]>(`/api/cards/topics?userId=${userId}`),
  attempt: (
    cardId: string,
    userId: string,
    rating: 1 | 2 | 3 | 4,
    user_answer?: string,
    source: DueCard['source'] = 'capsule',
  ) =>
    req<{ card_id: string; next_review_at: string; interval_days: number; ease_factor: number }>(
      source === 'topic' ? `/api/cards/topic/${cardId}/attempt` : `/api/cards/${cardId}/attempt`,
      { method: 'POST', body: JSON.stringify({ user_id: userId, rating, user_answer: user_answer ?? '' }) }
    ),
  stats: (userId: string, topicId?: string) =>
    req<CardStats>(`/api/cards/stats?userId=${userId}${topicId ? `&topicId=${topicId}` : ''}`),
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
    req<MasteryProgress>(`/api/mastery/progress?userId=${userId}${topic ? `&topic=${topic}` : ''}`),
  nextFocus: (userId: string, topic?: string) =>
    req<{ concept: string; mastery_level: string; reason: string }>(
      `/api/mastery/next?userId=${userId}${topic ? `&topic=${topic}` : ''}`
    ),
}

// ── Topics ──
export type TopicFolder = {
  id: string
  user_id: string
  name: string
  created_at: string
}

export type Topic = {
  id: string
  user_id: string
  name: string
  status: 'active' | 'completed'
  started_at: string
  folder_id?: string | null
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
  generateCapsule: (topicId: string, userId: string, chatMessages?: { role: string; content: string }[], existingCapsuleId?: string, lang: string = 'auto') =>
    req<{ topic_id: string; capsule_id: string; status: string }>(
      `/api/topics/${topicId}/capsule/generate`,
      { method: 'POST', body: JSON.stringify({
        user_id: userId,
        chat_messages: chatMessages ?? null,
        existing_capsule_id: existingCapsuleId ?? null,
        lang,
      }) }
    ),
  capsuleEventsUrl: (topicId: string, capsuleId: string) =>
    sseUrl(`/api/topics/${topicId}/capsule/events?capsule_id=${capsuleId}`),
  update: (topicId: string, data: { name?: string; folderId?: string | null }) =>
    req<Topic>(`/api/topics/${topicId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name: data.name, folder_id: data.folderId }),
    }),
}

export const folders = {
  list: (userId: string) =>
    req<TopicFolder[]>(`/api/topic-folders?user_id=${userId}`),
  create: (userId: string, name: string) =>
    req<TopicFolder>('/api/topic-folders', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, name }),
    }),
  rename: (folderId: string, name: string) =>
    req<TopicFolder>(`/api/topic-folders/${folderId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
  delete: (folderId: string) =>
    req<void>(`/api/topic-folders/${folderId}`, { method: 'DELETE' }),
}

// ── Capsules ──
export type Capsule = {
  id: string
  user_id: string
  topic_id: string
  content_md: string
  content_html: string
  summary: string
  title?: string | null
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
  list: (userId: string, topicId?: string) =>
    req<Capsule[]>(`/api/capsules?user_id=${userId}${topicId ? `&topic_id=${topicId}` : ''}`),
  update: (id: string, title: string) =>
    req<Capsule>(`/api/capsules/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
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

// ── Onboarding (adaptive pre-topic interview) ──
export type OnboardingOption = { value: string; label: string }
export type OnboardingSlot = {
  id: string
  question: string
  multiselect: boolean
  allow_free_text: boolean
  options: OnboardingOption[]
}
export type StudyProfile = {
  goal: string
  known_concepts: string[]
  focus_subtopics: string[]
  conspect_format: string[]
  task_format: string[]
  depth: string
  difficulty: string
  include_diagrams: boolean
  theory_practice_ratio: string
}

export const onboarding = {
  questions: (userId: string, topicId: string, lang: string = 'auto') =>
    req<{ domain: string; slots: OnboardingSlot[] }>('/api/onboarding/questions', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, topic_id: topicId, lang }),
    }),
  plan: (userId: string, topicId: string, answers: Record<string, string | string[]>, lang: string = 'auto') =>
    req<{ plan_md: string; study_profile: StudyProfile }>('/api/onboarding/plan', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, topic_id: topicId, answers, lang }),
    }),
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

export type Attachment = {
  id: string
  submission_id: string
  name: string
  mime_type: string
  kind: 'text' | 'image'
  file_size: number | null
  created_at: string
}

export type AnswerSubmissionResult = {
  submission: IdeSubmission
  evaluation: Evaluation
  follow_ups: FollowUp[]
  attachments: Attachment[]
}

export const practice = {
  startSession: (userId: string, topicId: string, studyProfile?: StudyProfile | { preset?: string } & Record<string, unknown>, lang: string = 'auto') =>
    req<{
      session: StudySession
      tasks: PracticeTask[]
      generation_status: 'generating' | 'ai' | 'fallback'
      generation_error: string | null
    }>('/api/study-sessions', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, topic_id: topicId, study_profile: studyProfile ?? null, lang }),
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
  submitAnswer: async (
    taskId: string,
    userId: string,
    solutionText: string,
    files: File[] = [],
  ): Promise<AnswerSubmissionResult> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('grasp_token') : null
    const form = new FormData()
    form.append('user_id', userId)
    form.append('solution_text', solutionText)
    for (const file of files) form.append('files', file)
    const res = await fetch(`${BASE}/api/practice-tasks/${taskId}/answer`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Submit error')
    }
    return res.json()
  },
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

export type ChatAttachment = {
  id: string
  name: string
  mime_type: string
  kind: 'text' | 'image'
  file_size: number | null
  data_url: string | null
}

export type ChatMessage = {
  id: string
  session_id: string
  role: string
  content: string
  created_at: string
  attachments?: ChatAttachment[]
}

export type ChatTurn = {
  user_message: ChatMessage
  assistant_message: ChatMessage
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
  turn: async (
    sessionId: string,
    userId: string,
    message: string,
    history: { role: string; content: string }[],
    files: File[] = [],
    lang: string = 'auto',
  ): Promise<ChatTurn> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('grasp_token') : null
    const form = new FormData()
    form.append('user_id', userId)
    form.append('message', message)
    form.append('history_json', JSON.stringify(history))
    form.append('lang', lang)
    for (const file of files) form.append('files', file)
    const res = await fetch(`${BASE}/api/chat/sessions/${sessionId}/turn`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Chat error')
    }
    return res.json()
  },
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
  renameSession: (sessionId: string, title: string) =>
    req<ChatSession>(`/api/chat/sessions/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),
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
