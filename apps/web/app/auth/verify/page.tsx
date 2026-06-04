'use client'

import { useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { auth } from '@/lib/api'
import { saveSession } from '@/lib/auth'
import { Suspense } from 'react'

function VerifyContent() {
  const params = useSearchParams()
  const router = useRouter()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    const token = params.get('token')
    if (!token) {
      setStatus('error')
      setErrorMsg('Ссылка недействительна — токен не найден.')
      return
    }

    auth.verify(token)
      .then((data) => {
        saveSession(data.access_token, {
          user_id: data.user_id,
          email: data.email,
          display_name: data.display_name,
        })
        setStatus('success')
        setTimeout(() => router.replace('/dashboard'), 1200)
      })
      .catch((err) => {
        setStatus('error')
        setErrorMsg(err.message ?? 'Ссылка недействительна или уже использована.')
      })
  }, [params, router])

  if (status === 'loading') {
    return (
      <div className="text-center">
        <div className="w-12 h-12 rounded-full border-2 border-line border-t-accent animate-spin mx-auto mb-6" />
        <h2 className="font-display text-2xl font-bold text-ink mb-2">Входим...</h2>
        <p className="text-mute">Проверяем ссылку</p>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="text-center">
        <div className="w-16 h-16 rounded-2xl bg-accentsoft flex items-center justify-center mx-auto mb-6">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent))" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </div>
        <h2 className="font-display text-2xl font-bold text-ink mb-2">Добро пожаловать!</h2>
        <p className="text-mute">Переходим на главную...</p>
      </div>
    )
  }

  return (
    <div className="text-center">
      <div className="w-16 h-16 rounded-2xl bg-danger/10 flex items-center justify-center mx-auto mb-6">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="rgb(var(--danger))" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <h2 className="font-display text-2xl font-bold text-ink mb-3">Ссылка не работает</h2>
      <p className="text-mute mb-6 max-w-xs mx-auto">{errorMsg}</p>
      <a
        href="/login"
        className="inline-block px-6 py-3 rounded-xl bg-accent text-[#06140d] font-semibold hover:bg-accentdk transition-colors"
      >
        Запросить новую ссылку
      </a>
    </div>
  )
}

export default function VerifyPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-5">
      <a href="https://proof-forge.ru" className="flex items-center gap-2.5 mb-12">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="rgb(var(--accent))" strokeWidth="2"/>
          <circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/>
        </svg>
        <span className="font-display text-xl font-bold text-ink">Grasp</span>
      </a>
      <Suspense fallback={<div className="w-8 h-8 rounded-full border-2 border-t-accent border-line animate-spin" />}>
        <VerifyContent />
      </Suspense>
    </div>
  )
}
