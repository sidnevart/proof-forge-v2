import { test, expect } from '@playwright/test'
import { createTestUser, createTopic } from './helpers'

test('cards page loads without errors', async ({ page }) => {
  test.slow() // Allow extra time for first load with webServer
  await createTestUser(page, 'CardsFlow')

  // Navigate to cards page
  await page.goto('/cards')

  // Wait for loading skeleton to disappear
  await page.waitForTimeout(2000)

  // Page should have an h1 heading (either the cards page title or results screen)
  const heading = page.locator('h1').first()
  await expect(heading).toBeVisible({ timeout: 5000 })
})
