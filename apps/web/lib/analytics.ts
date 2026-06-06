/**
 * Typed business event tracker.
 * All app events go through here — keeps instrumentation consistent.
 */

import { analytics } from './api'

export type AppEvent =
  | { name: 'page_view'; props: { path: string } }
  | { name: 'login_attempt'; props?: Record<string, never> }
  | { name: 'magic_link_sent'; props?: Record<string, never> }
  | { name: 'topic_creation_started'; props: { has_materials: boolean; file_count: number; link_count: number } }
  | { name: 'capsule_generation_started'; props: { material_count: number } }
  | { name: 'capsule_viewed'; props: { capsule_id: string } }
  | { name: 'ai_feedback_clicked'; props: { capsule_id: string } }
  | { name: 'card_session_start'; props: { due_count: number; topic?: string } }
  | { name: 'card_session_end'; props: { reviewed: number; easy_pct: number; streak: number } }
  | { name: 'card_rated'; props: { rating: 1 | 2 | 3 | 4; topic?: string } }
  | { name: 'dashboard_viewed'; props: { due_cards: number; has_capsules: boolean } }

let _sid: string | null = null

function sid(): string {
  if (!_sid) {
    _sid = typeof window !== 'undefined'
      ? (localStorage.getItem('g-sid') ?? generateSid())
      : 'ssr'
  }
  return _sid
}

function generateSid(): string {
  const s = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)
  localStorage.setItem('g-sid', s)
  return s
}

export function track(event: AppEvent): void {
  if (typeof window === 'undefined') return
  const { name, props } = event
  analytics.track(sid(), name, props as Record<string, unknown> ?? {})
}
