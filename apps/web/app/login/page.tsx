'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { auth } from '@/lib/api'
import { isLoggedIn, saveSession } from '@/lib/auth'
import { track } from '@/lib/analytics'
import { useT } from '@/lib/i18n'
import { LocaleToggle } from '@/components/LocaleToggle'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const t = useT()

  useEffect(() => {
    if (isLoggedIn()) router.replace('/dashboard')
  }, [router])

  // Handle VS Code auth token injected via postMessage
  useEffect(() => {
    const handleMessage = async (e: MessageEvent) => {
      if (e.data?.type !== 'auth_token' || !e.data.token) return
      try {
        localStorage.setItem('grasp_token', e.data.token)
        const user = await auth.me()
        saveSession(e.data.token, { user_id: user.user_id, email: user.email, display_name: user.display_name })
        router.replace('/dashboard')
      } catch {}
    }
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return
    setLoading(true)
    setError('')
    track({ name: 'login_attempt' })
    try {
      await auth.sendLink(email.trim(), name.trim())
      setSent(true)
      track({ name: 'magic_link_sent' })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t('login.errorFallback'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-5 py-12 relative">
      {/* Language toggle */}
      <div className="absolute top-4 right-4">
        <LocaleToggle />
      </div>

      {/* Logo */}
      <a href="https://proof-forge.ru" className="flex items-center gap-2.5 mb-12 group">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="rgb(var(--accent))" strokeWidth="2"/>
          <circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/>
        </svg>
        <span className="font-display text-2xl font-bold text-ink group-hover:text-accent transition-colors">Grasp</span>
      </a>

      <div className="w-full max-w-sm">
        {!sent ? (
          <>
            <h1 className="font-display text-3xl font-bold text-ink mb-2">{t('login.title')}</h1>
            <p className="text-mute mb-8">{t('login.subtitle')}</p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-mute mb-1.5">{t('login.nameLabel')}</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t('login.namePlaceholder')}
                  className="w-full px-4 py-3 rounded-xl border border-line bg-card text-ink placeholder:text-mute/60 focus:outline-none focus:border-accent/60 transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-mute mb-1.5">{t('login.emailLabel')}</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoFocus
                  className="w-full px-4 py-3 rounded-xl border border-line bg-card text-ink placeholder:text-mute/60 focus:outline-none focus:border-accent/60 transition-colors"
                />
              </div>

              {error && (
                <p className="text-sm text-danger bg-danger/10 border border-danger/20 px-4 py-2.5 rounded-xl">{error}</p>
              )}

              <button
                type="submit"
                disabled={loading || !email.trim()}
                className="w-full py-3.5 rounded-xl bg-accent text-[#06140d] font-semibold btn-press hover:bg-accentdk transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? t('login.sending') : t('login.submit')}
              </button>
            </form>

            <p className="mt-6 text-xs text-center text-mute">
              {t('login.noAccount')}
            </p>
          </>
        ) : (
          <div className="text-center">
            <div className="w-16 h-16 rounded-2xl bg-accentsoft flex items-center justify-center mx-auto mb-6">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                <polyline points="22,6 12,13 2,6"/>
              </svg>
            </div>
            <h2 className="font-display text-2xl font-bold text-ink mb-3">{t('login.sent.title')}</h2>
            <p className="text-mute mb-2">
              {t('login.sent.check')} <span className="text-ink font-medium">{email}</span> {t('login.sent.suffix')}
            </p>
            <p className="text-sm text-mute">{t('login.sent.expiry')}</p>
            <button
              onClick={() => setSent(false)}
              className="mt-8 text-sm text-accent hover:text-accentdk transition-colors"
            >
              {t('login.sent.change')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
