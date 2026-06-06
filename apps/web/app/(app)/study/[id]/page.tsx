'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { getStoredUser } from '@/lib/auth'
import { practice, chat, topics, capsules, type PracticeTask, type StudySession, type ChatMessage, type ChatSession, type Capsule, type AnswerSubmissionResult } from '@/lib/api'
import { SkeletonText } from '@/components/ui/Skeleton'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { useT } from '@/lib/i18n'
import { useSSEStream } from '@/hooks/useSSEStream'
import { useDrawer } from '@/lib/drawer-context'
import { CHAT_ACCEPT, PendingChip, MessageAttachment } from '@/app/(app)/_components/file-chip'

const MAX_CHAT_FILES = 5
const MAX_CHAT_FILE_BYTES = 8_000_000

type Tab = 'chat' | 'theory' | 'practice' | 'capsule'

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
  const [chatFiles, setChatFiles] = useState<File[]>([])
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<Tab>('chat')
  const chatFileRef = useRef<HTMLInputElement>(null)

  // Capsule generation state
  const [capsule, setCapsule] = useState<Capsule | null>(null)
  const [isGeneratingCapsule, setIsGeneratingCapsule] = useState(false)
  const [capsuleGenError, setCapsuleGenError] = useState('')
  const [capsuleEventsUrl2, setCapsuleEventsUrl2] = useState<string | null>(null)
  const pendingCapsuleId = useRef<string | null>(null)
  const [chatInitError, setChatInitError] = useState('')
  const [chatError, setChatError] = useState('')

  // Practice tab: selected task for inline view
  const [selectedTask, setSelectedTask] = useState<PracticeTask | null>(null)
  const [solution, setSolution] = useState('')
  const [attachFiles, setAttachFiles] = useState<File[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [evalResult, setEvalResult] = useState<AnswerSubmissionResult | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Streaming state for generating sessions
  const [streamingConspect, setStreamingConspect] = useState('')
  const [streamingPhase, setStreamingPhase] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState('')

  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { openDrawer } = useDrawer()

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
      // progress events received — no step counter needed
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

  // Reset selected task when switching away from practice tab
  useEffect(() => {
    if (activeTab !== 'practice') {
      setSelectedTask(null)
      setSolution('')
      setAttachFiles([])
      setEvalResult(null)
      setSubmitError('')
    }
  }, [activeTab])

  const submitAnswer = useCallback(async () => {
    if (!selectedTask || !user || submitting) return
    if (!solution.trim() && attachFiles.length === 0) return
    setSubmitting(true)
    setSubmitError('')
    try {
      const result = await practice.submitAnswer(selectedTask.id, user.user_id, solution, attachFiles)
      setEvalResult(result)
      // Reflect the new task status (submitted/completed) in the list
      practice.listActiveTasks(user.user_id)
        .then((all) => setTasks(all.filter((t) => t.study_session_id === id)))
        .catch(() => {})
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : t('practice.submitError'))
    } finally {
      setSubmitting(false)
    }
  }, [selectedTask, user, submitting, solution, attachFiles, id, t])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if ((!text && chatFiles.length === 0) || sending || !user || !chatSession) return

    const filesToSend = [...chatFiles]
    setInput('')
    setChatFiles([])
    setSending(true)
    setChatError('')

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }))
      const res = await chat.turn(chatSession.id, user.user_id, text, history, filesToSend)
      setMessages((prev) => [...prev, res.user_message, res.assistant_message])
    } catch (err) {
      setChatError(getChatErrorMessage(err, t))
    } finally {
      setSending(false)
      textareaRef.current?.focus()
    }
  }, [input, chatFiles, sending, user, chatSession, messages, t])

  const handleChatFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? [])
    if (chatFileRef.current) chatFileRef.current.value = ''
    const oversized = picked.filter((f) => f.size > MAX_CHAT_FILE_BYTES)
    if (oversized.length) { setChatError(t('chat.attach.tooBig')); return }
    setChatFiles((prev) => {
      const next = [...prev, ...picked]
      if (next.length > MAX_CHAT_FILES) { setChatError(t('chat.attach.tooMany')); return prev }
      return next
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (input.trim() || chatFiles.length > 0) sendMessage()
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

  const TABS = ['chat', 'theory', 'practice', 'capsule'] as const

  return (
    <div className="flex flex-col h-[calc(100dvh-5rem)] md:h-[100dvh] max-h-[100dvh] overflow-hidden">
      {/* Header — hamburger on mobile, back arrow always visible */}
      <div className="shrink-0 border-b border-line px-4 py-3 flex items-center gap-3 bg-paper/80 backdrop-blur-md z-10">
        {/* Hamburger — mobile only, opens the drawer */}
        <button
          onClick={openDrawer}
          className="md:hidden w-8 h-8 rounded-lg border border-line flex items-center justify-center text-ink hover:text-accent transition-colors shrink-0"
          aria-label="Open menu"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6" x2="21" y2="6"/>
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <Link href="/dashboard" className="text-mute hover:text-ink transition-colors shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </Link>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-ink truncate">
            {session.conspect_md.slice(0, 60).replace(/^#+\s*/, '') || t('study.sessionFallback')}
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="shrink-0 flex border-b border-line bg-paper overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 min-w-fit px-4 py-2.5 text-xs font-medium transition-colors whitespace-nowrap ${
              activeTab === tab
                ? 'text-accent border-b-2 border-accent bg-accentsoft/20'
                : 'text-mute border-b-2 border-transparent hover:text-ink'
            }`}
          >
            {t(`study.tab.${tab}`)}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {/* ── Chat tab ── */}
        {activeTab === 'chat' && (
          <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {isStreaming && messages.length === 0 && (
                <div className="max-w-md mx-auto text-center py-12">
                  <div className="w-12 h-12 rounded-2xl bg-accentsoft border border-accent/20 flex items-center justify-center mx-auto mb-3">
                    <div className="w-5 h-5 rounded-full border-2 border-accentdk border-t-accent animate-spin" />
                  </div>
                  <p className="text-sm font-medium text-ink mb-1">AI готовит материал</p>
                  <p className="text-xs text-mute font-mono">{streamingPhase || 'Подожди немного...'}</p>
                  <p className="text-xs text-mute mt-2">Конспект уже пишется на вкладке Теория →</p>
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
                    {msg.attachments && msg.attachments.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {msg.attachments.map((att) => (
                          <MessageAttachment key={att.id} att={att} />
                        ))}
                      </div>
                    )}
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
              <input
                ref={chatFileRef}
                type="file"
                multiple
                accept={CHAT_ACCEPT}
                className="hidden"
                onChange={handleChatFiles}
              />
              {chatFiles.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2 max-w-3xl mx-auto">
                  {chatFiles.map((file, idx) => (
                    <PendingChip
                      key={`${file.name}-${idx}`}
                      file={file}
                      onRemove={() => setChatFiles((prev) => prev.filter((_, i) => i !== idx))}
                    />
                  ))}
                </div>
              )}
              <div className="flex gap-2 items-end max-w-3xl mx-auto">
                <button
                  type="button"
                  onClick={() => chatFileRef.current?.click()}
                  disabled={sending || !chatSession}
                  title={t('chat.attach')}
                  className="w-9 h-9 rounded-xl border border-line bg-card flex items-center justify-center text-mute hover:text-ink hover:border-accent/40 transition-colors disabled:opacity-40 shrink-0"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
                  </svg>
                </button>
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
                  disabled={(!input.trim() && chatFiles.length === 0) || sending || !chatSession}
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
        )}

        {/* ── Theory tab ── */}
        {activeTab === 'theory' && (
          <div className="h-full overflow-y-auto">
            <div className="max-w-3xl mx-auto p-4 md:p-6">
              {isStreaming && streamingPhase && (
                <div className="flex items-center gap-2 mb-4">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse shrink-0" />
                  <span className="text-xs font-mono text-accent">{streamingPhase}</span>
                </div>
              )}
              {streamError && (
                <div className="mb-4 px-3 py-2 rounded-lg bg-danger/10 border border-danger/20 text-xs text-danger">
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
          </div>
        )}

        {/* ── Practice tab ── */}
        {activeTab === 'practice' && (
          <div className="h-full overflow-y-auto">
            <div className="max-w-3xl mx-auto p-4 md:p-6">
              {/* Inline task detail */}
              {selectedTask ? (
                <div>
                  <button
                    onClick={() => { setSelectedTask(null); setSolution(''); setAttachFiles([]); setEvalResult(null); setSubmitError('') }}
                    className="text-sm text-mute hover:text-ink font-mono mb-4 inline-flex items-center gap-1"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="15 18 9 12 15 6"/>
                    </svg>
                    {t('practice.back')}
                  </button>
                  <div className="mb-6">
                    <div className="text-xs font-mono text-accent mb-2">{selectedTask.type}</div>
                    <h1 className="font-display text-2xl font-bold text-ink">{selectedTask.title}</h1>
                  </div>
                  <div className="surface rounded-2xl p-5 mb-6">
                    <MarkdownRenderer>{selectedTask.instructions_md}</MarkdownRenderer>
                  </div>
                  <div className="surface rounded-2xl p-5 mb-6">
                    <label className="text-xs font-mono text-mute mb-2 block">
                      {t('practice.submit')}
                    </label>
                    <textarea
                      rows={8}
                      value={solution}
                      onChange={(e) => setSolution(e.target.value)}
                      placeholder={t('practice.submitHint')}
                      disabled={submitting}
                      className="w-full resize-y rounded-xl border border-line bg-card text-ink placeholder:text-mute/50 px-4 py-3 text-sm font-mono focus:outline-none focus:border-accent/60 transition-colors disabled:opacity-50"
                    />

                    {/* File attachments */}
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept="image/png,image/jpeg,image/webp,image/gif,.pdf,.md,.txt,.py,.js,.ts,.go,.rs,.java,.c,.cpp,.h,.json,.yaml,.yml,.csv,.sql,.sh,.kt,.rb,.php"
                      className="hidden"
                      onChange={(e) => {
                        const picked = Array.from(e.target.files ?? [])
                        if (picked.length) setAttachFiles((prev) => [...prev, ...picked])
                        if (fileInputRef.current) fileInputRef.current.value = ''
                      }}
                    />
                    <div className="mt-3 flex items-center gap-2 flex-wrap">
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={submitting}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-line text-xs text-mute hover:text-ink hover:border-accent/60 transition-colors disabled:opacity-50"
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                        </svg>
                        {t('practice.attach')}
                      </button>
                      <span className="text-[10px] text-mute/70">{t('practice.attachHint')}</span>
                    </div>
                    {attachFiles.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {attachFiles.map((file, idx) => (
                          <div key={`${file.name}-${idx}`} className="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg bg-card border border-line text-xs">
                            <span className="text-ink truncate">{file.name}</span>
                            <button
                              type="button"
                              onClick={() => setAttachFiles((prev) => prev.filter((_, i) => i !== idx))}
                              disabled={submitting}
                              className="text-mute hover:text-danger transition-colors shrink-0"
                              aria-label="Remove file"
                            >
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                              </svg>
                            </button>
                          </div>
                        ))}
                      </div>
                    )}

                    {submitError && (
                      <div className="mt-3 px-3 py-2 rounded-lg bg-danger/10 border border-danger/20 text-xs text-danger">
                        {submitError}
                      </div>
                    )}

                    <button
                      onClick={submitAnswer}
                      disabled={submitting || (!solution.trim() && attachFiles.length === 0)}
                      className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-accent text-[#06140d] text-sm font-semibold hover:bg-accentdk transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {submitting ? (
                        <>
                          <div className="w-3.5 h-3.5 rounded-full border-2 border-[#06140d] border-t-transparent animate-spin" />
                          {t('practice.submitting')}
                        </>
                      ) : (
                        evalResult ? t('practice.resubmit') : t('practice.submit')
                      )}
                    </button>
                  </div>

                  {/* AI feedback */}
                  {evalResult && (
                    <div className="surface rounded-2xl p-5 mb-6">
                      <div className="flex items-center justify-between gap-3 mb-3">
                        <div className="text-[10px] font-mono text-accent uppercase tracking-wider">{t('practice.feedback')}</div>
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                            evalResult.evaluation.status === 'passed'
                              ? 'bg-accent/10 text-accent'
                              : evalResult.evaluation.status === 'needs_revision'
                              ? 'bg-sand text-mute'
                              : 'bg-danger/10 text-danger'
                          }`}>
                            {t(`practice.status.${evalResult.evaluation.status}`)}
                          </span>
                          <span className="text-xs font-mono text-mute">
                            {t('practice.score')}: {Math.round(evalResult.evaluation.score * 100)}%
                          </span>
                        </div>
                      </div>
                      <div className="prose-grasp text-sm">
                        <MarkdownRenderer>{evalResult.evaluation.feedback_md}</MarkdownRenderer>
                      </div>
                      {evalResult.follow_ups.length > 0 && (
                        <div className="mt-4 pt-4 border-t border-line">
                          <div className="text-xs font-semibold text-ink mb-2">{t('practice.followUps')}</div>
                          <ul className="list-disc list-inside space-y-1 text-xs text-ink/90">
                            {evalResult.follow_ups.map((fu) => (
                              <li key={fu.id}>{fu.question}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <>
                  {isStreaming && tasks.length === 0 && (
                    <div className="flex items-center gap-2 py-8 justify-center">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                      <span className="text-xs text-mute font-mono">Создаю задания...</span>
                    </div>
                  )}
                  {!isStreaming && tasks.length === 0 && (
                    <div className="text-center py-12">
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
                  <div className="space-y-3">
                    {tasks.map((task) => (
                      <button
                        key={task.id}
                        onClick={() => { setSelectedTask(task); setSolution(''); setAttachFiles([]); setEvalResult(null); setSubmitError('') }}
                        className="surface surface-hover rounded-xl p-4 block w-full text-left"
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
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── Capsule tab ── */}
        {activeTab === 'capsule' && (
          <div className="h-full overflow-y-auto">
            <div className="max-w-3xl mx-auto p-4 md:p-6">
              {/* Capsule generation error */}
              {capsuleGenError && (
                <div className="px-3 py-2 rounded-lg bg-danger/10 border border-danger/20 text-xs text-danger mb-4">
                  {capsuleGenError}
                </div>
              )}

              {/* Existing capsule */}
              {capsule ? (
                <div className="space-y-4">
                  <div className="surface rounded-xl p-4">
                    <div className="text-[10px] font-mono text-accent uppercase tracking-wider mb-1.5">Капсула</div>
                    <p className="text-sm font-medium text-ink mb-3 leading-snug">{capsule.summary}</p>
                    <Link
                      href={`/capsule/${capsule.id}`}
                      className="inline-flex items-center gap-1 text-xs text-accent hover:text-accentdk transition-colors font-mono"
                    >
                      {t('study.capsuleCta')}
                    </Link>
                  </div>
                </div>
              ) : (
                /* No capsule yet — create button */
                <div className="text-center py-12">
                  <div className="w-12 h-12 rounded-2xl bg-accentsoft border border-accent/20 flex items-center justify-center mx-auto mb-3">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
                      <rect x="3" y="3" width="18" height="18" rx="3"/>
                      <line x1="9" y1="9" x2="15" y2="9"/>
                      <line x1="9" y1="13" x2="15" y2="13"/>
                      <line x1="9" y1="17" x2="12" y2="17"/>
                    </svg>
                  </div>
                  <p className="text-sm text-mute mb-4 max-w-xs mx-auto leading-relaxed">
                    {t('study.capsule.empty')}
                  </p>
                  <button
                    onClick={handleGenerateCapsule}
                    disabled={isGeneratingCapsule || isStreaming}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-accent text-[#06140d] text-sm font-semibold hover:bg-accentdk transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isGeneratingCapsule ? (
                      <>
                        <div className="w-3.5 h-3.5 rounded-full border-2 border-[#06140d] border-t-transparent animate-spin" />
                        {t('study.generating')}
                      </>
                    ) : (
                      t('study.createCapsule')
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
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
