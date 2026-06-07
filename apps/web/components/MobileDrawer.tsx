'use client'

import { useEffect, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { getStoredUser } from '@/lib/auth'
import { practice, type StudySession } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { LocaleToggle } from '@/components/LocaleToggle'

interface MobileDrawerProps {
  open: boolean
  onClose: () => void
  user: { display_name: string; email: string }
}

export function MobileDrawer({ open, onClose, user }: MobileDrawerProps) {
  const pathname = usePathname()
  const [sessions, setSessions] = useState<StudySession[]>([])
  const [mounted, setMounted] = useState(false)
  const t = useT()

  useEffect(() => { setMounted(true) }, [])

  // Load study sessions — re-fetch on navigation so newly created lessons appear
  // without a manual reload.
  useEffect(() => {
    const stored = getStoredUser()
    if (!stored) return
    practice.listSessions(stored.user_id).then(setSessions).catch(() => {})
  }, [pathname])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  // Close on route change
  useEffect(() => { onClose() }, [pathname])

  const navItems = [
    { href: '/dashboard', label: t('nav.home') },
    { href: '/cards', label: t('nav.cards') },
    { href: '/progress', label: t('nav.progress') },
    { href: '/capsules', label: t('nav.capsules') },
  ]

  if (!mounted) return null

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-[100] bg-black/60 transition-opacity duration-300 ${
          open ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div
        className={`fixed top-0 left-0 bottom-0 w-72 max-w-[85vw] z-[101] bg-paper border-r border-line shadow-xl transition-transform duration-300 ease-out safe-area-bottom ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-4 py-5 border-b border-line flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-2.5" onClick={onClose}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9" stroke="rgb(var(--accent))" strokeWidth="2"/>
              <circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/>
            </svg>
            <span className="font-display text-xl font-bold text-ink">Grasp</span>
          </Link>
          <button onClick={onClose} className="text-mute hover:text-ink p-1 transition-colors" aria-label="Close menu">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* Nav items */}
        <nav className="px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + '/')
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={`nav-item ${active ? 'active' : ''}`}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>

        {/* Study sessions */}
        <div className="px-3 py-2 border-t border-line/60">
          <div className="px-2 py-1 text-[10px] font-mono text-mute uppercase tracking-wider">
            {t('nav.sessions')}
          </div>
          <div className="space-y-0.5 mt-1 max-h-[30vh] overflow-y-auto">
            {sessions.slice(0, 15).map((s) => {
              const active = pathname === `/study/${s.id}`
              const title = s.conspect_md.slice(0, 40).replace(/^#+\s*/, '') || t('nav.sessionFallback')
              return (
                <Link
                  key={s.id}
                  href={`/study/${s.id}`}
                  onClick={onClose}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs transition-colors ${
                    active ? 'bg-accentsoft text-accent font-medium' : 'text-mute hover:text-ink hover:bg-card'
                  }`}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.2" fill="currentColor"/>
                  </svg>
                  <span className="truncate">{title}</span>
                </Link>
              )
            })}
          </div>
        </div>

        {/* Locale toggle + user */}
        <div className="px-3 py-4 border-t border-line mt-auto">
          <div className="flex items-center gap-2.5 px-2 py-2 mb-2">
            <div className="w-7 h-7 rounded-lg bg-accentsoft flex items-center justify-center text-accent text-xs font-bold">
              {user.display_name[0]?.toUpperCase() ?? '?'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-ink truncate">{user.display_name}</div>
              <div className="text-xs text-mute truncate">{user.email}</div>
            </div>
          </div>
          <div className="flex justify-center">
            <LocaleToggle />
          </div>
        </div>
      </div>
    </>,
    document.body
  )
}
