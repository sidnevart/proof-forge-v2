'use client'

export type AuthUser = {
  user_id: string
  email: string
  display_name: string
}

export function saveSession(token: string, user: AuthUser) {
  localStorage.setItem('grasp_token', token)
  localStorage.setItem('grasp_user', JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem('grasp_token')
  localStorage.removeItem('grasp_user')
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem('grasp_user')
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

export function getSessionId(): string {
  if (typeof window === 'undefined') return 'ssr'
  let sid = localStorage.getItem('g-sid')
  if (!sid) {
    sid = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2)
    localStorage.setItem('g-sid', sid)
  }
  return sid
}

export function isLoggedIn(): boolean {
  if (typeof window === 'undefined') return false
  return !!localStorage.getItem('grasp_token')
}
