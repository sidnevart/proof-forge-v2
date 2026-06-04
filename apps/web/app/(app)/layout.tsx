'use client'

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { AppSidebar, AppBottomNav } from '@/components/AppNav'
import { getStoredUser, type AuthUser } from '@/lib/auth'
import { track } from '@/lib/analytics'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [checked, setChecked] = useState(false)

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
      <main className={`flex-1 min-w-0 pb-20 md:pb-0 ${fixedViewport ? 'h-dvh overflow-hidden' : ''}`}>
        {children}
      </main>
      <AppBottomNav />
    </div>
  )
}
