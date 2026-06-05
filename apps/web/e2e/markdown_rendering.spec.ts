import { test, expect } from '@playwright/test'
import { createTestUser, createTopic, addMaterial } from './helpers'

test('capsule page renders markdown content without errors', async ({ page }) => {
  test.slow()
  const API = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000'
  const user = await createTestUser(page, 'MarkdownE2E')
  const topic = await createTopic(page, user.user_id, 'React hooks')

  // Add a material so capsule generation has content to work with
  await addMaterial(
    page,
    topic.id,
    user.user_id,
    '# React hooks\n\nuseState and useEffect are the most common hooks.\n\n```jsx\nconst [count, setCount] = useState(0)\n```\n',
    'React hooks overview',
  )

  // Generate capsule (works in fallback mode without LLM key)
  const genRes = await page.request.post(
    `${API}/api/topics/${topic.id}/capsule/generate`,
    { data: { user_id: user.user_id } },
  )
  expect(genRes.ok()).toBeTruthy()
  const genBody = await genRes.json()
  const capsuleId = genBody.capsule_id
  expect(capsuleId).toBeTruthy()

  // Poll until capsule is ready (background task, longer timeout for safety)
  let capsule = null
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(500)
    const getRes = await page.request.get(`${API}/api/capsules/${capsuleId}`)
    if (getRes.ok()) {
      capsule = await getRes.json()
      if (capsule.status === 'ready') break
    }
  }
  expect(capsule).not.toBeNull()
  // If capsule isn't ready, log the status for debugging
  if (capsule && capsule.status !== 'ready') {
    console.log('Capsule status:', capsule.status, 'summary:', capsule.summary)
  }
  expect(capsule?.status).toBe('ready')
  expect((capsule?.content_md?.length ?? 0)).toBeGreaterThan(10)

  // Navigate to capsule page
  await page.goto(`/capsule/${capsuleId}`)
  await page.waitForLoadState('networkidle')

  // Wait for React to render (loading skeleton → content)
  await page.waitForTimeout(2000)

  // Verify the page rendered content
  await page.screenshot({ path: 'test-results/capsule-page.png' })

  // Check that markdown headings are rendered (h2 elements exist)
  const headingCount = await page.locator('h2').count()
  expect(headingCount).toBeGreaterThan(0)

  // Verify no error state
  const errorText = page.getByText(/^(Session not found|Capsule not found|Not found|Не найдена)$/)
  const hasError = await errorText.count()
  expect(hasError).toBe(0)
})
