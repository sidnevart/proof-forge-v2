'use client'

import { use, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getStoredUser } from '@/lib/auth'
import { chat, topics, type Topic } from '@/lib/api'

type Message = { role: 'user' | 'assistant'; content: string }

export default function LearnPage({ params }: { params: Promise<{ topic_id: string }> }) {
  const { topic_id } = use(params)
  const user = getStoredUser()
  const [topic, setTopic] = useState<Topic | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    topics.get(topic_id).then(setTopic).catch(console.error)
  }, [topic_id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const send = async () => {
    const text = input.trim()
    if (!text || sending || !user) return

    const userMsg: Message = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setSending(true)

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }))
      const res = await chat.send(user.user_id, text, history, topic_id)
      setMessages((prev) => [...prev, { role: 'assistant', content: res.message }])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Ошибка: ${err instanceof Error ? err.message : 'что-то пошло не так'}` },
      ])
    } finally {
      setSending(false)
      textareaRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="flex flex-col h-screen max-h-screen">
      {/* Header */}
      <div className="shrink-0 border-b border-line px-5 py-3 flex items-center gap-3">
        <Link
          href="/dashboard"
          className="text-mute hover:text-ink transition-colors"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </Link>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-mono text-accent">Ментор</div>
          <div className="text-sm font-semibold text-ink truncate">
            {topic?.name ?? 'Загрузка...'}
          </div>
        </div>
        <div className="text-xs font-mono text-mute/60 hidden sm:block">Enter ↵ отправить · Shift+Enter новая строка</div>
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
            <h2 className="font-display text-xl font-bold text-ink mb-2">Привет! Я твой ментор.</h2>
            <p className="text-mute text-sm">
              Задавай вопросы по теме, проси объяснить концепцию, дать задание или разобрать код.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
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
              {msg.role === 'assistant' ? (
                <div className="prose-grasp text-sm">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ children }) => <h1 className="font-display text-lg font-bold text-ink mt-4 mb-2">{children}</h1>,
                      h2: ({ children }) => <h2 className="font-display text-base font-bold text-ink mt-3 mb-1.5">{children}</h2>,
                      h3: ({ children }) => <h3 className="font-semibold text-ink mt-2 mb-1">{children}</h3>,
                      p: ({ children }) => <p className="text-ink/90 leading-relaxed mb-2 last:mb-0">{children}</p>,
                      code: ({ children, className }) =>
                        className ? (
                          <code className="code-surface block p-3 rounded-xl font-mono text-xs my-2 overflow-x-auto whitespace-pre">
                            {children}
                          </code>
                        ) : (
                          <code className="font-mono text-accent bg-accentsoft px-1 py-0.5 rounded text-xs">{children}</code>
                        ),
                      ul: ({ children }) => <ul className="list-disc list-inside space-y-0.5 mb-2 text-ink/90">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal list-inside space-y-0.5 mb-2 text-ink/90">{children}</ol>,
                      blockquote: ({ children }) => (
                        <blockquote className="border-l-2 border-accent pl-3 my-2 text-mute italic text-sm">{children}</blockquote>
                      ),
                      strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
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
        <div className="flex gap-2 items-end max-w-3xl mx-auto">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Спроси ментора..."
            rows={1}
            disabled={sending}
            className="flex-1 resize-none px-4 py-3 rounded-xl border border-line bg-card text-ink placeholder:text-mute/50 focus:outline-none focus:border-accent/60 transition-colors text-sm disabled:opacity-50"
            style={{ maxHeight: '120px', overflowY: 'auto' }}
            onInput={(e) => {
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = Math.min(el.scrollHeight, 120) + 'px'
            }}
          />
          <button
            onClick={send}
            disabled={!input.trim() || sending}
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
