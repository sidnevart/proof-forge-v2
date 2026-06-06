'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { clearSession } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { practice, topics, folders, type StudySession, type Topic, type TopicFolder } from '@/lib/api'
import { getStoredUser } from '@/lib/auth'
import { useT } from '@/lib/i18n'
import { LocaleToggle } from '@/components/LocaleToggle'

const NAV_ICONS = [
  (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
  ),
  (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="5" width="20" height="14" rx="3"/>
      <path d="M6 9h4M6 13h8"/>
    </svg>
  ),
  (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="3"/>
      <line x1="9" y1="9" x2="15" y2="9"/>
      <line x1="9" y1="13" x2="15" y2="13"/>
      <line x1="9" y1="17" x2="12" y2="17"/>
    </svg>
  ),
]

const NAV_HREFS = ['/dashboard', '/cards', '/progress', '/capsules']

export function AppSidebar({ user }: { user: { display_name: string; email: string } }) {
  const pathname = usePathname()
  const router = useRouter()
  const storedUser = getStoredUser()
  const [studySessions, setStudySessions] = useState<StudySession[]>([])
  const [allTopics, setAllTopics] = useState<Topic[]>([])
  const [allFolders, setAllFolders] = useState<TopicFolder[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  // Folder creation inline
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  // Collapsed folders
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const t = useT()

  const navItems = [
    { href: NAV_HREFS[0], label: t('nav.home'), icon: NAV_ICONS[0] },
    { href: NAV_HREFS[1], label: t('nav.cards'), icon: NAV_ICONS[1] },
    { href: NAV_HREFS[2], label: t('nav.progress'), icon: NAV_ICONS[2] },
    { href: NAV_HREFS[3], label: t('nav.capsules'), icon: NAV_ICONS[3] },
  ]

  useEffect(() => {
    if (!storedUser) return
    Promise.all([
      practice.listSessions(storedUser.user_id),
      topics.list(storedUser.user_id),
      folders.list(storedUser.user_id),
    ])
      .then(([sessions, topicList, folderList]) => {
        setStudySessions(sessions)
        setAllTopics(topicList)
        setAllFolders(folderList)
      })
      .catch(() => {})
      .finally(() => setSessionsLoading(false))
  }, [storedUser?.user_id])

  const handleCreateFolder = async () => {
    if (!storedUser || !newFolderName.trim()) return
    const folder = await folders.create(storedUser.user_id, newFolderName.trim())
    setAllFolders((prev) => [...prev, folder])
    setNewFolderName('')
    setCreatingFolder(false)
  }

  const toggleCollapse = (id: string) =>
    setCollapsed((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s })

  const handleLogout = () => {
    clearSession()
    router.push('/login')
  }

  // Map topicId → latest study session
  const sessionByTopic = studySessions.reduce<Record<string, StudySession>>((acc, s) => {
    if (!acc[s.topic_id]) acc[s.topic_id] = s
    return acc
  }, {})

  const unfoldered = allTopics.filter((tp) => !tp.folder_id)

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
          {t('nav.newTopic')}
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + '/')
          return (
            <Link key={item.href} href={item.href} className={`nav-item ${active ? 'active' : ''}`}>
              {item.icon}
              {item.label}
            </Link>
          )
        })}

        {/* Topics with folders */}
        <div className="pt-3 mt-2 border-t border-line/60">
          <div className="flex items-center px-2 py-1 mb-1">
            <span className="text-[10px] font-mono text-mute uppercase tracking-wider flex-1">{t('nav.sessions')}</span>
            <button
              onClick={() => setCreatingFolder(true)}
              title="Новая папка"
              className="text-mute hover:text-ink transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
                <line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>
              </svg>
            </button>
          </div>

          {/* New folder input */}
          {creatingFolder && (
            <div className="flex gap-1 px-2 mb-1">
              <input
                autoFocus
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleCreateFolder(); if (e.key === 'Escape') setCreatingFolder(false) }}
                placeholder="Имя папки"
                className="flex-1 text-xs px-2 py-1 rounded-lg border border-line bg-card text-ink focus:outline-none focus:border-accent/60"
              />
              <button onClick={handleCreateFolder} className="text-accent text-xs px-1">✓</button>
              <button onClick={() => setCreatingFolder(false)} className="text-mute text-xs px-1">✕</button>
            </div>
          )}

          {sessionsLoading ? (
            <div className="px-2 py-1.5 text-xs text-mute animate-pulse">{t('nav.loading')}</div>
          ) : (
            <div className="space-y-0.5">
              {/* Folders */}
              {allFolders.map((folder) => {
                const folderTopics = allTopics.filter((tp) => tp.folder_id === folder.id)
                const isCollapsed = collapsed.has(folder.id)
                return (
                  <div key={folder.id}>
                    <button
                      onClick={() => toggleCollapse(folder.id)}
                      className="flex items-center gap-1.5 w-full px-2 py-1.5 rounded-lg text-xs text-mute hover:text-ink hover:bg-card transition-colors"
                    >
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`shrink-0 transition-transform ${isCollapsed ? '' : 'rotate-90'}`}>
                        <polyline points="9 18 15 12 9 6"/>
                      </svg>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0">
                        <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
                      </svg>
                      <span className="truncate font-medium">{folder.name}</span>
                      <span className="ml-auto text-[10px] opacity-50">{folderTopics.length}</span>
                    </button>
                    {!isCollapsed && folderTopics.map((tp) => {
                      const s = sessionByTopic[tp.id]
                      const href = s ? `/study/${s.id}` : `/topics/${tp.id}`
                      const active = pathname.startsWith(`/study/${s?.id}`) || pathname === `/topics/${tp.id}`
                      return (
                        <Link key={tp.id} href={href} className={`flex items-center gap-2 pl-7 pr-2 py-1.5 rounded-lg text-xs transition-colors ${active ? 'bg-accentsoft text-accent font-medium' : 'text-mute hover:text-ink hover:bg-card'}`}>
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.2" fill="currentColor"/></svg>
                          <span className="truncate">{tp.name}</span>
                        </Link>
                      )
                    })}
                  </div>
                )
              })}

              {/* Unfoldered topics */}
              {unfoldered.slice(0, 8).map((tp) => {
                const s = sessionByTopic[tp.id]
                const href = s ? `/study/${s.id}` : `/topics/${tp.id}`
                const active = pathname.startsWith(`/study/${s?.id}`) || pathname === `/topics/${tp.id}`
                return (
                  <Link key={tp.id} href={href} className={`flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs transition-colors ${active ? 'bg-accentsoft text-accent font-medium' : 'text-mute hover:text-ink hover:bg-card'}`}>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.2" fill="currentColor"/></svg>
                    <span className="truncate">{tp.name}</span>
                  </Link>
                )
              })}

              {allTopics.length === 0 && allFolders.length === 0 && (
                <div className="px-2 py-1.5 text-xs text-mute/60">{t('nav.noSessions')}</div>
              )}
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
          {t('nav.logout')}
        </button>
        <div className="mt-2 flex justify-center">
          <LocaleToggle />
        </div>
      </div>
    </aside>
  )
}

export function AppBottomNav() {
  const pathname = usePathname()
  const t = useT()

  const navItems = [
    { href: NAV_HREFS[0], label: t('nav.home'), icon: NAV_ICONS[0] },
    { href: NAV_HREFS[1], label: t('nav.cards'), icon: NAV_ICONS[1] },
    { href: NAV_HREFS[2], label: t('nav.progress'), icon: NAV_ICONS[2] },
    { href: NAV_HREFS[3], label: t('nav.capsules'), icon: NAV_ICONS[3] },
  ]

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 border-t border-line bg-paper/90 backdrop-blur-md safe-area-bottom">
      <div className="flex items-center justify-around px-2 py-2">
        {navItems.map((item) => {
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
          <span className="text-[10px] font-medium text-accent">{t('nav.learn')}</span>
        </Link>
      </div>
    </nav>
  )
}
