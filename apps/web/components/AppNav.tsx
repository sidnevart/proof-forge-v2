'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { clearSession } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { practice, type StudySession } from '@/lib/api'
import { getStoredUser } from '@/lib/auth'

const NAV_ITEMS = [
  {
    href: '/dashboard',
    label: 'Главная',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
      </svg>
    ),
  },
  {
    href: '/cards',
    label: 'Карточки',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="5" width="20" height="14" rx="3"/>
        <path d="M6 9h4M6 13h8"/>
      </svg>
    ),
  },
  {
    href: '/progress',
    label: 'Прогресс',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    ),
  },
]

export function AppSidebar({ user }: { user: { display_name: string; email: string } }) {
  const pathname = usePathname()
  const router = useRouter()
  const storedUser = getStoredUser()
  const [studySessions, setStudySessions] = useState<StudySession[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)

  useEffect(() => {
    if (!storedUser) return
    practice.listSessions(storedUser.user_id)
      .then(setStudySessions)
      .catch(() => {})
      .finally(() => setSessionsLoading(false))
  }, [storedUser?.user_id])

  const handleLogout = () => {
    clearSession()
    router.push('/login')
  }

  const isStudyActive = pathname.startsWith('/study/') || pathname.startsWith('/practice/')

  return (
    <aside className="hidden md:flex flex-col w-56 shrink-0 h-screen sticky top-0 border-r border-line bg-sand/30">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-line">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="rgb(var(--accent))" strokeWidth="2"/>
            <circle cx="12" cy="12" r="3.2" fill="rgb(var(--accent))"/>
          </svg>
          <span className="font-display text-xl font-bold text-ink">Grasp</span>
        </Link>
      </div>

      {/* New Topic CTA */}
      <div className="px-3 pt-4 pb-2">
        <Link
          href="/topics/new"
          className="flex items-center gap-2 w-full px-3 py-2.5 rounded-xl bg-accent text-[#06140d] font-semibold text-sm hover:bg-accentdk transition-colors"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Новая тема
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + '/')
          return (
            <Link key={item.href} href={item.href} className={`nav-item ${active ? 'active' : ''}`}>
              {item.icon}
              {item.label}
            </Link>
          )
        })}

        {/* Study sessions */}
        <div className="pt-3 mt-2 border-t border-line/60">
          <div className="px-2 py-1 text-[10px] font-mono text-mute uppercase tracking-wider mb-1">
            Сессии обучения
          </div>
          {sessionsLoading ? (
            <div className="px-2 py-1.5 text-xs text-mute animate-pulse">Загрузка...</div>
          ) : studySessions.length === 0 ? (
            <div className="px-2 py-1.5 text-xs text-mute/60">Нет активных сессий</div>
          ) : (
            <div className="space-y-0.5">
              {studySessions.slice(0, 6).map((s) => {
                const active = pathname === `/study/${s.id}`
                const title = s.conspect_md.slice(0, 40).replace(/^#+\s*/, '') || 'Сессия'
                return (
                  <Link
                    key={s.id}
                    href={`/study/${s.id}`}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs transition-colors ${
                      active ? 'bg-accentsoft text-accent font-medium' : 'text-mute hover:text-ink hover:bg-card'
                    }`}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.2" fill="currentColor"/>
                    </svg>
                    <span className="truncate">{title}</span>
                    {s.status === 'completed' && <span className="ml-auto text-[9px] opacity-50">✓</span>}
                  </Link>
                )
              })}
            </div>
          )}
        </div>
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-line">
        <div className="flex items-center gap-2.5 px-2 py-2">
          <div className="w-7 h-7 rounded-lg bg-accentsoft flex items-center justify-center text-accent text-xs font-bold">
            {user.display_name[0]?.toUpperCase() ?? '?'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-ink truncate">{user.display_name}</div>
            <div className="text-xs text-mute truncate">{user.email}</div>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full mt-1 text-left nav-item text-mute hover:text-danger"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
          Выйти
        </button>
      </div>
    </aside>
  )
}

export function AppBottomNav() {
  const pathname = usePathname()
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 border-t border-line bg-paper/90 backdrop-blur-md safe-area-bottom">
      <div className="flex items-center justify-around px-2 py-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + '/')
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-1 px-4 py-1.5 rounded-xl transition-all ${
                active ? 'text-accent' : 'text-mute hover:text-ink'
              }`}
            >
              {item.icon}
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          )
        })}
        {/* New Topic — center action */}
        <Link
          href="/topics/new"
          className="flex flex-col items-center gap-1 px-4 py-1.5"
        >
          <div className="w-8 h-8 rounded-xl bg-accent flex items-center justify-center text-[#06140d]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </div>
          <span className="text-[10px] font-medium text-accent">Учиться</span>
        </Link>
      </div>
    </nav>
  )
}
