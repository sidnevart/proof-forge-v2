'use client'

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { AppSidebar, AppBottomNav } from '@/components/AppNav'
import { MobileDrawer } from '@/components/MobileDrawer'
import { getStoredUser, type AuthUser } from '@/lib/auth'
import { track } from '@/lib/analytics'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [checked, setChecked] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => {
    const stored = getStoredUser()
    if (!stored) {
      router.replace('/login')
    } else {
      setUser(stored)
    }
    setChecked(true)
  }, [router])

  useEffect(() => {
    if (checked && user) {
      track({ name: 'page_view', props: { path: pathname } })
    }
  }, [pathname, checked, user])

  const fixedViewport =
    pathname.startsWith('/study/') || pathname.startsWith('/learn/')

  if (!checked || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-line border-t-accent animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen">
      <AppSidebar user={user} />

      {/* Mobile drawer */}
      <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} user={user} />

      {/* Hamburger button — mobile only */}
      <button
        onClick={() => setDrawerOpen(true)}
        className="md:hidden fixed top-3 left-3 z-40 w-9 h-9 rounded-xl bg-paper/90 backdrop-blur border border-line flex items-center justify-center text-ink hover:text-accent transition-colors"
        aria-label="Open menu"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="3" y1="6" x2="21" y2="6"/>
          <line x1="3" y1="12" x2="21" y2="12"/>
          <line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>

      <main className={`flex-1 min-w-0 pb-20 md:pb-0 ${fixedViewport ? 'h-dvh overflow-hidden' : ''}`}>
        {children}
      </main>
      <AppBottomNav />
    </div>
  )
}
