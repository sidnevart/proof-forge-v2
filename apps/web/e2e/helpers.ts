import type { Page } from '@playwright/test'

const API_URL = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000'
const COUNTER = { value: 0 }

/** Unique per-run email so parallel test-worker runs don't collide on the same user. */
export function uniqueEmail(prefix = 'e2e') {
  COUNTER.value += 1
  return `${prefix}-${Date.now()}-${COUNTER.value}@test.proof-forge`
}

export interface TestUser {
  user_id: string
  email: string
  display_name: string
  access_token: string
}

/** Create a user via the dev-token endpoint and inject auth into localStorage. */
export async function createTestUser(page: Page, displayName = 'E2E User'): Promise<TestUser> {
  const email = uniqueEmail('e2e-user')
  const res = await page.request.post(`${API_URL}/api/auth/dev-token`, {
    data: { email, display_name: displayName },
  })
  if (!res.ok()) {
    throw new Error(`dev-token failed: ${res.status()} ${await res.text()}`)
  }
  const body = await res.json()

  // Navigate to the app first so localStorage is accessible on the correct origin
  await page.goto('/')
  await page.evaluate(
    ({ token, user }) => {
      localStorage.setItem('grasp_token', token)
      localStorage.setItem('grasp_user', JSON.stringify(user))
    },
    {
      token: body.access_token,
      user: { user_id: body.user_id, email: body.email, display_name: body.display_name },
    },
  )

  return {
    user_id: body.user_id,
    email: body.email,
    display_name: body.display_name,
    access_token: body.access_token,
  }
}

/** Create a topic via the backend API. */
export async function createTopic(
  page: Page,
  userId: string,
  name: string,
): Promise<{ id: string; name: string }> {
  const res = await page.request.post(`${API_URL}/api/topics/start`, {
    data: { user_id: userId, name },
  })
  if (!res.ok()) throw new Error(`topic create failed: ${res.status()} ${await res.text()}`)
  return res.json()
}

/** Add a text material to a topic. */
export async function addMaterial(
  page: Page,
  topicId: string,
  userId: string,
  content: string,
  name = 'Test Material',
) {
  const res = await page.request.post(`${API_URL}/api/topics/${topicId}/materials/file?user_id=${userId}`, {
    multipart: {
      file: {
        name: 'material.md',
        mimeType: 'text/markdown',
        buffer: Buffer.from(content, 'utf-8'),
      },
    },
  })
  if (!res.ok()) throw new Error(`add material failed: ${res.status()} ${await res.text()}`)
}

/** Create review cards from a capsule for the user. */
export async function createCardsFromCapsule(page: Page, userId: string, capsuleId: string) {
  const res = await page.request.post(`${API_URL}/api/cards/from-capsule`, {
    data: { user_id: userId, capsule_id: capsuleId },
  })
  if (!res.ok()) throw new Error(`create cards failed: ${res.status()} ${await res.text()}`)
  return res.json()
}

/** Create a study session (returns immediately, background runs). */
export async function createStudySession(page: Page, userId: string, topicId: string) {
  const res = await page.request.post(`${API_URL}/api/study-sessions`, {
    data: { user_id: userId, topic_id: topicId },
  })
  if (!res.ok()) throw new Error(`study session failed: ${res.status()} ${await res.text()}`)
  return res.json()
}

/** Get a capsule for a topic (returns first found or null). */
export async function getTopicCapsule(page: Page, userId: string, topicId: string) {
  const res = await page.request.get(
    `${API_URL}/api/capsules?user_id=${userId}&topic_id=${topicId}`,
  )
  if (!res.ok()) return null
  const capsules = await res.json()
  return capsules[0] ?? null
}

/** Get the topic card. Returns card data or null. */
export async function getTopicCard(page: Page, cardId: string) {
  const res = await page.request.get(`${API_URL}/api/cards/due?userId=${cardId}&limit=10`)
  if (!res.ok()) return null
  return res.json()
}
