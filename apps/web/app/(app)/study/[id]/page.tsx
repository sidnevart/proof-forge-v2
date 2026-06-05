'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { getStoredUser } from '@/lib/auth'
import { practice, chat, topics, capsules, type PracticeTask, type StudySession, type ChatMessage, type ChatSession, type Capsule } from '@/lib/api'
import { SkeletonText } from '@/components/ui/Skeleton'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { useT } from '@/lib/i18n'
import { useSSEStream } from '@/hooks/useSSEStream'

type Tab = 'chat' | 'materials'

export default function StudySessionPage() {
  const { id } = useParams<{ id: string }>()
  const searchParams = useSearchParams()
  const user = getStoredUser()
  const t = useT()

  const [session, setSession] = useState<StudySession | null>(null)
  const [tasks, setTasks] = useState<PracticeTask[]>([])
  const [chatSession, setChatSession] = useState<ChatSession | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<Tab>('chat')

  // Capsule generation state
  const [capsule, setCapsule] = useState<Capsule | null>(null)
  const [isGeneratingCapsule, setIsGeneratingCapsule] = useState(false)
  const [capsuleGenError, setCapsuleGenError] = useState('')
  const [capsuleEventsUrl2, setCapsuleEventsUrl2] = useState<string | null>(null)
  const pendingCapsuleId = useRef<string | null>(null)
  const [chatInitError, setChatInitError] = useState('')
  const [chatError, setChatError] = useState('')

  // Streaming state for generating sessions
  const [streamingConspect, setStreamingConspect] = useState('')
  const [streamingPhase, setStreamingPhase] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState('')

  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // SSE stream for generating sessions
  useSSEStream(
    isStreaming ? practice.sessionEventsUrl(id) : null,
    (event) => {
      if (event.type === 'phase_change') {
        setStreamingPhase((event.data.label as string) ?? '')
      } else if (event.type === 'token') {
        setStreamingConspect((prev) => prev + ((event.data.content as string) ?? ''))
      } else if (event.type === 'task_ready') {
        const task = event.data as unknown as PracticeTask
        setTasks((prev) => {
          if (prev.some((t) => t.id === task.id)) return prev
          return [...prev, task]
        })
      } else if (event.type === 'complete') {
        setIsStreaming(false)
        // Reload session to get final conspect_md and status
        practice.getSession(id).then((s) => {
          setSession(s)
          setStreamingConspect('')
        }).catch(() => {})
        practice.listActiveTasks(user?.user_id ?? '').then((all) => {
          setTasks(all.filter((t) => t.study_session_id === id))
        }).catch(() => {})
      } else if (event.type === 'error') {
        setStreamError((event.data.message as string) ?? 'Ошибка генерации')
        setIsStreaming(false)
      }
    }
  )

  // SSE stream for capsule generation
  useSSEStream(capsuleEventsUrl2, (event) => {
    if (event.type === 'progress') {
      // progress events received — no step counter needed in this minimal UI
    } else if (event.type === 'complete') {
      setCapsuleEventsUrl2(null)
      const cid = (event.data.capsule_id as string) ?? pendingCapsuleId.current
      if (cid) {
        capsules.get(cid).then((c) => {
          setCapsule(c)
          setIsGeneratingCapsule(false)
        }).catch(() => setIsGeneratingCapsule(false))
      }
    } else if (event.type === 'error') {
      setCapsuleEventsUrl2(null)
      setCapsuleGenError((event.data.message as string) ?? 'Ошибка генерации')
      setIsGeneratingCapsule(false)
    }
  })

  // Load study session, tasks, and chat
  useEffect(() => {
    if (!user) return
    Promise.all([
      practice.getSession(id),
      practice.listActiveTasks(user.user_id),
    ]).then(async ([s, activeTasks]) => {
      setSession(s)
      setTasks(activeTasks.filter((task) => task.study_session_id === s.id))
      if (s.status === 'generating') {
        setIsStreaming(true)
        setStreamingPhase('Готовлю материал...')
      }

      // Load or create chat session
      try {
        const sessions = await chat.listSessions(user.user_id)
        const existing = sessions.find((cs) => cs.study_session_id === s.id)
        if (existing) {
          setChatSession(existing)
          const msgs = await chat.listMessages(existing.id)
          setMessages(msgs)
        } else {
          const newSession = await chat.createSession(user.user_id, s.topic_id, s.conspect_md.slice(0, 60), s.id)
          setChatSession(newSession)
        }
      } catch (e) {
        setChatInitError(e instanceof Error ? e.message : t('study.chatError'))
      }
    }).finally(() => setLoading(false))
  }, [id, user?.user_id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || sending || !user || !chatSession) return

    setInput('')
    setSending(true)
    setChatError('')

    // Save user message
    try {
      await chat.createMessage(chatSession.id, 'user', text)
    } catch {
      // ignore save error, still show locally
    }
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), session_id: chatSession.id, role: 'user', content: text, created_at: new Date().toISOString() }])

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }))
      const res = await chat.send(user.user_id, text, history, chatSession.topic_id)
      // Save assistant message
      try {
        await chat.createMessage(chatSession.id, 'assistant', res.message)
      } catch {}
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), session_id: chatSession.id, role: 'assistant', content: res.message, created_at: new Date().toISOString() }])
    } catch (err) {
      setChatError(getChatErrorMessage(err, t))
    } finally {
      setSending(false)
      textareaRef.current?.focus()
    }
  }, [input, sending, user, chatSession, messages, t])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleGenerateCapsule = async () => {
    if (!session || !user || isGeneratingCapsule) return
    setIsGeneratingCapsule(true)
    setCapsuleGenError('')
    try {
      const chatMessages = messages.map((m) => ({ role: m.role, content: m.content }))
      const result = await topics.generateCapsule(session.topic_id, user.user_id, chatMessages)
      pendingCapsuleId.current = result.capsule_id
      setCapsuleEventsUrl2(topics.capsuleEventsUrl(session.topic_id, result.capsule_id))
    } catch (err) {
      setCapsuleGenError(err instanceof Error ? err.message : 'Ошибка генерации')
      setIsGeneratingCapsule(false)
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-5 py-8">
        <SkeletonText lines={8} />
      </div>
    )
  }

  if (!session) {
    return (
      <div className="max-w-3xl mx-auto px-5 py-16 text-center text-mute">
        {t('study.notFound')}
      </div>
    )
  }

  const generationFallback = searchParams.get('generation') === 'fallback'
  const generationReason = searchParams.get('reason')

  return (
    <div className="flex flex-col h-[calc(100dvh-5rem)] md:h-[100dvh] max-h-[100dvh] overflow-hidden">
      {/* Header */}
      <div className="shrink-0 border-b border-line px-4 py-3 flex items-center gap-3 bg-paper/80 backdrop-blur-md z-10">
        <Link href="/dashboard" className="text-mute hover:text-ink transition-colors shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </Link>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-mono text-accent truncate">Study Session</div>
          <div className="text-sm font-semibold text-ink truncate">
            {session.conspect_md.slice(0, 60).replace(/^#+\s*/, '') || t('study.sessionFallback')}
          </div>
        </div>
      </div>

      {/* Mobile tabs */}
      <div className="md:hidden shrink-0 flex border-b border-line bg-paper">
        {(['chat', 'materials'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2.5 text-xs font-medium transition-colors ${
              activeTab === tab ? 'text-accent border-b-2 border-accent bg-accentsoft/20' : 'text-mute'
            }`}
          >
            {tab === 'chat' ? t('study.tab.chat') : t('study.tab.materials')}
          </button>
        ))}
      </div>

      {/* Main content area */}
      <div className="flex-1 min-h-0 flex flex-col md:flex-row">
        {/* Chat panel */}
        <div className={`flex-1 flex flex-col min-h-0 md:border-r border-line ${activeTab !== 'chat' ? 'hidden md:flex' : ''}`}>
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {isStreaming && messages.length === 0 && (
              <div className="max-w-md mx-auto text-center py-12">
                <div className="w-12 h-12 rounded-2xl bg-accentsoft border border-accent/20 flex items-center justify-center mx-auto mb-3">
                  <div className="w-5 h-5 rounded-full border-2 border-accentdk border-t-accent animate-spin" />
                </div>
                <p className="text-sm font-medium text-ink mb-1">AI готовит материал</p>
                <p className="text-xs text-mute font-mono">{streamingPhase || 'Подожди немного...'}</p>
                <p className="text-xs text-mute mt-2">Конспект уже пишется на вкладке справа →</p>
              </div>
            )}
            {!isStreaming && messages.length === 0 && !sending && (
              <div className="max-w-md mx-auto text-center py-12">
                <div className="w-12 h-12 rounded-2xl bg-accentsoft border border-accent/20 flex items-center justify-center mx-auto mb-3">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
                    <circle cx="12" cy="12" r="9"/>
                    <circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/>
                  </svg>
                </div>
                <h2 className="font-display text-lg font-bold text-ink mb-1">{t('study.mentor.title')}</h2>
                <p className="text-mute text-xs">{t('study.mentor.empty')}</p>
              </div>
            )}

            {chatInitError && (
              <div className="px-3 py-2 rounded-lg bg-danger/10 border border-danger/20 text-xs text-danger">
                {chatInitError}
              </div>
            )}

            {generationFallback && (
              <div className="px-3 py-2 rounded-lg bg-danger/10 border border-danger/20 text-xs text-danger">
                {t('study.fallback')}
                {generationReason ? ` Reason: ${generationReason}` : ''}
              </div>
            )}

            {chatError && (
              <div className="px-3 py-2 rounded-lg bg-danger/10 border border-danger/20 text-xs text-danger">
                {chatError}
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'assistant' && (
                  <div className="w-6 h-6 rounded-md bg-accentsoft border border-accent/20 flex items-center justify-center shrink-0 mr-2 mt-1">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
                      <circle cx="12" cy="12" r="9"/>
                      <circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/>
                    </svg>
                  </div>
                )}
                <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm ${
                  msg.role === 'user'
                    ? 'bg-card border border-line text-ink rounded-tr-sm'
                    : 'bg-sand/40 border border-line/60 text-ink rounded-tl-sm'
                }`}>
                  {msg.role === 'assistant' ? (
                    <div className="prose-grasp">
                      <MarkdownRenderer
                        components={{
                          h1: ({ children }) => <h1 className="font-display text-base font-bold text-ink mt-3 mb-1">{children}</h1>,
                          h2: ({ children }) => <h2 className="font-display text-sm font-bold text-ink mt-2 mb-1">{children}</h2>,
                          h3: ({ children }) => <h3 className="font-semibold text-ink mt-1.5 mb-0.5 text-xs">{children}</h3>,
                          p: ({ children }) => <p className="text-ink/90 leading-relaxed mb-1.5 last:mb-0">{children}</p>,
                          ul: ({ children }) => <ul className="list-disc list-inside space-y-0.5 mb-1.5 text-ink/90 text-xs">{children}</ul>,
                          ol: ({ children }) => <ol className="list-decimal list-inside space-y-0.5 mb-1.5 text-ink/90 text-xs">{children}</ol>,
                        }}
                      >
                        {msg.content}
                      </MarkdownRenderer>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}

            {sending && (
              <div className="flex justify-start">
                <div className="w-6 h-6 rounded-md bg-accentsoft border border-accent/20 flex items-center justify-center shrink-0 mr-2 mt-1">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
                    <circle cx="12" cy="12" r="9"/>
                    <circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/>
                  </svg>
                </div>
                <div className="bg-sand/40 border border-line/60 rounded-2xl rounded-tl-sm px-3.5 py-2.5">
                  <div className="flex gap-1 items-center h-4">
                    <span className="w-1 h-1 rounded-full bg-accent animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1 h-1 rounded-full bg-accent animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1 h-1 rounded-full bg-accent animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="shrink-0 border-t border-line px-3 py-2.5">
            <div className="flex gap-2 items-end max-w-3xl mx-auto">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('study.input.placeholder')}
                rows={1}
                disabled={sending || !chatSession}
                className="flex-1 h-9 resize-none overflow-hidden px-3 py-2 rounded-xl border border-line bg-card text-ink placeholder:text-mute/50 focus:outline-none focus:border-accent/60 transition-colors text-sm leading-5 disabled:opacity-50"
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || sending || !chatSession}
                className="w-9 h-9 rounded-xl bg-accent flex items-center justify-center text-[#06140d] hover:bg-accentdk transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="22" y1="2" x2="11" y2="13"/>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Right panel: conspect + tasks */}
        <div className={`w-full md:w-[380px] lg:w-[420px] shrink-0 flex flex-col min-h-0 bg-sand/20 border-l border-line ${activeTab !== 'materials' ? 'hidden md:flex' : ''}`}>
          {/* Panel header with "Создать конспект" */}
          <div className="shrink-0 flex items-center justify-between px-4 py-2.5 border-b border-line">
            <span className="text-xs font-mono text-mute uppercase tracking-wider">Materials</span>
            <button
              onClick={handleGenerateCapsule}
              disabled={isGeneratingCapsule || isStreaming}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-accentsoft border border-accent/30 text-accent text-xs font-medium hover:bg-accent hover:text-[#06140d] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGeneratingCapsule ? (
                <>
                  <div className="w-3 h-3 rounded-full border border-current border-t-transparent animate-spin" />
                  Генерируется...
                </>
              ) : 'Создать конспект'}
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            {/* Capsule result / generation state */}
            {capsuleGenError && (
              <div className="px-4 pt-3 pb-0">
                <div className="px-3 py-2 rounded-lg bg-danger/10 border border-danger/20 text-xs text-danger">
                  {capsuleGenError}
                </div>
              </div>
            )}
            {capsule && (
              <div className="p-4 border-b border-line">
                <div className="text-[10px] font-mono text-accent uppercase tracking-wider mb-1.5">Конспект готов</div>
                <p className="text-sm font-medium text-ink mb-2 leading-snug">{capsule.summary}</p>
                <Link
                  href={`/capsule/${capsule.id}`}
                  className="inline-flex items-center gap-1 text-xs text-accent hover:text-accentdk transition-colors font-mono"
                >
                  Открыть полный конспект →
                </Link>
              </div>
            )}

            <div className="p-4">
              {/* Streaming phase label */}
              {isStreaming && streamingPhase && (
                <div className="flex items-center gap-2 mb-3 px-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse shrink-0" />
                  <span className="text-xs font-mono text-accent">{streamingPhase}</span>
                </div>
              )}
              {streamError && (
                <div className="mb-3 px-3 py-2 rounded-lg bg-danger/10 border border-danger/20 text-xs text-danger">
                  {streamError} — показан шаблонный контент.
                </div>
              )}
              <div className="prose-grasp text-sm">
                <MarkdownRenderer>
                  {streamingConspect || session.conspect_md}
                </MarkdownRenderer>
                {isStreaming && (
                  <span className="inline-block w-0.5 h-4 bg-accent animate-pulse ml-0.5 align-middle" />
                )}
              </div>
            </div>

            <div className="p-4 space-y-2 border-t border-line">
              {isStreaming && tasks.length === 0 && (
                <div className="flex items-center gap-2 py-8 justify-center">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                  <span className="text-xs text-mute font-mono">Создаю задания...</span>
                </div>
              )}
              {!isStreaming && tasks.length === 0 && (
                <div className="text-center py-8">
                  {session?.status === 'generating' ? (
                    <p className="text-xs text-mute">{t('study.tasksLoading')}</p>
                  ) : (
                    <>
                      <p className="text-xs text-mute mb-2">{t('study.noTasks')}</p>
                      <button
                        onClick={() => window.location.reload()}
                        className="text-xs text-accent hover:text-accentdk underline"
                      >
                        Обновить страницу
                      </button>
                    </>
                  )}
                </div>
              )}
              {tasks.map((task) => (
                <Link
                  key={task.id}
                  href={`/practice/${task.id}`}
                  className="surface surface-hover rounded-xl p-3.5 block text-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-[10px] font-mono text-accent uppercase tracking-wide">{task.type}</div>
                      <div className="font-semibold text-ink mt-0.5">{task.title}</div>
                      <div className="text-xs text-mute mt-1 line-clamp-2">{task.instructions_md.slice(0, 120)}...</div>
                    </div>
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0 ${
                      task.status === 'completed'
                        ? 'bg-accent/10 text-accent'
                        : task.status === 'submitted'
                        ? 'bg-sand text-mute'
                        : 'bg-card border border-line text-mute'
                    }`}>
                      {task.status}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function getChatErrorMessage(err: unknown, t: (k: string) => string) {
  const message = err instanceof Error ? err.message : t('chat.fallback')
  if (message.includes('LLM не настроен') || message.includes('LLM not configured')) {
    return t('chat.err.notConfigured')
  }
  if (message.includes('LLM error')) {
    return `${t('chat.err.providerError')} ${message}`
  }
  if (message.includes('LLM timeout')) {
    return t('chat.err.timeout')
  }
  return `${t('chat.err.prefix')}: ${message}`
}
