'use client'

import { use, useEffect, useRef, useState, useCallback } from 'react'
import Link from 'next/link'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { getStoredUser } from '@/lib/auth'
import { chat, topics, type Topic, type ChatMessage, type ChatSession } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { useDrawer } from '@/lib/drawer-context'
import { CHAT_ACCEPT, PendingChip, MessageAttachment } from '@/app/(app)/_components/file-chip'
import { LIMITS, validateFiles, limitErrorMessage } from '@/lib/upload-limits'

export default function LearnPage({ params }: { params: Promise<{ topic_id: string }> }) {
  const { topic_id } = use(params)
  const user = getStoredUser()
  const [topic, setTopic] = useState<Topic | null>(null)
  const [chatSession, setChatSession] = useState<ChatSession | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [chatFiles, setChatFiles] = useState<File[]>([])
  const [sending, setSending] = useState(false)
  const [chatError, setChatError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const chatFileRef = useRef<HTMLInputElement>(null)
  const t = useT()
  const { openDrawer } = useDrawer()

  useEffect(() => {
    topics.get(topic_id).then(setTopic).catch(console.error)
  }, [topic_id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  // Lazily get-or-create a chat session for persistence.
  const ensureSession = useCallback(async (): Promise<ChatSession> => {
    if (chatSession) return chatSession
    if (!user) throw new Error('Not authenticated')
    const topicName = topic?.name ?? topic_id
    const newSession = await chat.createSession(user.user_id, topic_id, topicName)
    setChatSession(newSession)
    return newSession
  }, [chatSession, user, topic, topic_id])

  const send = useCallback(async () => {
    const text = input.trim()
    if ((!text && chatFiles.length === 0) || sending || !user) return

    const filesToSend = [...chatFiles]
    setInput('')
    setChatFiles([])
    setSending(true)
    setChatError('')

    // Optimistic user bubble — render immediately, reconcile on success, roll back on error.
    const tempId = `temp-${Date.now()}`
    const history = messages.map((m) => ({ role: m.role, content: m.content }))
    setMessages((prev) => [
      ...prev,
      { id: tempId, session_id: chatSession?.id ?? 'pending', role: 'user', content: text, created_at: new Date().toISOString() },
    ])

    try {
      const session = await ensureSession()
      const res = await chat.turn(session.id, user.user_id, text, history, filesToSend)
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== tempId),
        res.user_message,
        res.assistant_message,
      ])
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== tempId))
      setInput(text)
      setChatFiles(filesToSend)
      setChatError(getChatErrorMessage(err, t))
    } finally {
      setSending(false)
      textareaRef.current?.focus()
    }
  }, [input, chatFiles, sending, user, chatSession, messages, ensureSession, t])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (input.trim() || chatFiles.length > 0) send()
    }
  }

  const handleChatFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? [])
    if (chatFileRef.current) chatFileRef.current.value = ''
    if (picked.length === 0) return
    const res = validateFiles(picked, chatFiles.length, LIMITS.chatAttachment)
    if (!res.ok) { setChatError(limitErrorMessage(t, res, LIMITS.chatAttachment)); return }
    setChatFiles((prev) => [...prev, ...res.accepted])
  }

  return (
    <div className="flex flex-col h-[calc(100dvh-5rem)] md:h-[100dvh] max-h-[100dvh] overflow-hidden">
      {/* Header */}
      <div className="shrink-0 border-b border-line px-5 py-3 flex items-center gap-3">
        {/* Hamburger — mobile only */}
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
        <Link
          href="/dashboard"
          className="text-mute hover:text-ink transition-colors"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </Link>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-mono text-accent">{t('learn.mentor')}</div>
          <div className="text-sm font-semibold text-ink truncate">
            {topic?.name ?? t('learn.loading')}
          </div>
        </div>
        <div className="text-xs font-mono text-mute/60 hidden sm:block">{t('learn.hint')}</div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && !sending && (
          <div className="max-w-md mx-auto text-center py-16">
            <div className="w-14 h-14 rounded-2xl bg-accentsoft border border-accent/20 flex items-center justify-center mx-auto mb-4">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
                <circle cx="12" cy="12" r="9"/>
                <circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/>
              </svg>
            </div>
            <h2 className="font-display text-xl font-bold text-ink mb-2">{t('learn.empty.title')}</h2>
            <p className="text-mute text-sm">{t('learn.empty.desc')}</p>
          </div>
        )}

        {chatError && (
          <div className="max-w-3xl mx-auto px-3 py-2 rounded-lg bg-danger/10 border border-danger/20 text-xs text-danger">
            {chatError}
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-lg bg-accentsoft border border-accent/20 flex items-center justify-center shrink-0 mr-2 mt-1">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
                  <circle cx="12" cy="12" r="9"/>
                  <circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/>
                </svg>
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === 'user'
                  ? 'bg-card border border-line text-ink rounded-tr-sm'
                  : 'bg-sand/40 border border-line/60 text-ink rounded-tl-sm'
              }`}
            >
              {msg.attachments && msg.attachments.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {msg.attachments.map((att) => (
                    <MessageAttachment key={att.id} att={att} />
                  ))}
                </div>
              )}
              {msg.role === 'assistant' ? (
                <div className="prose-grasp text-sm">
                  <MarkdownRenderer
                    components={{
                      h1: ({ children }) => <h1 className="font-display text-lg font-bold text-ink mt-4 mb-2">{children}</h1>,
                      h2: ({ children }) => <h2 className="font-display text-base font-bold text-ink mt-3 mb-1.5">{children}</h2>,
                      h3: ({ children }) => <h3 className="font-semibold text-ink mt-2 mb-1">{children}</h3>,
                      p: ({ children }) => <p className="text-ink/90 leading-relaxed mb-2 last:mb-0">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc list-inside space-y-0.5 mb-2 text-ink/90">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal list-inside space-y-0.5 mb-2 text-ink/90">{children}</ol>,
                      blockquote: ({ children }) => (
                        <blockquote className="border-l-2 border-accent pl-3 my-2 text-mute italic text-sm">{children}</blockquote>
                      ),
                      strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
                    }}
                  >
                    {msg.content}
                  </MarkdownRenderer>
                </div>
              ) : (
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              )}
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-lg bg-accentsoft border border-accent/20 flex items-center justify-center shrink-0 mr-2 mt-1">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
                <circle cx="12" cy="12" r="9"/>
                <circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/>
              </svg>
            </div>
            <div className="bg-sand/40 border border-line/60 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1 items-center h-5">
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-line px-4 py-3">
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
            disabled={sending}
            title={t('chat.attach')}
            className="w-10 h-10 rounded-xl border border-line bg-card flex items-center justify-center text-mute hover:text-ink hover:border-accent/40 transition-colors disabled:opacity-40 shrink-0"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
            </svg>
          </button>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('learn.placeholder')}
            rows={1}
            disabled={sending}
            className="flex-1 h-10 resize-none overflow-hidden px-4 py-2.5 rounded-xl border border-line bg-card text-ink placeholder:text-mute/50 focus:outline-none focus:border-accent/60 transition-colors text-sm leading-5 disabled:opacity-50"
          />
          <button
            onClick={send}
            disabled={(!input.trim() && chatFiles.length === 0) || sending}
            className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center text-[#06140d] hover:bg-accentdk transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
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
