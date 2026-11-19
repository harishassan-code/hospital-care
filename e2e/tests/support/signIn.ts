import { expect, type Browser, type BrowserContext, type Page } from '@playwright/test'
import { ACCOUNTS, DEMO_PASSWORD, type Role } from './accounts'

/** One signed-in person: their own browser context, so their cookies never mix with another role's. */
export type Session = { role: Role; context: BrowserContext; page: Page }

/**
 * Signs a seeded login in through /login, as a person would, and waits for the staff workspace. A staff login lands
 * on /staff, and the sidebar appears once the signed-in user's data has loaded.
 */
export async function signIn(browser: Browser, role: Role): Promise<Session> {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto('/login')
  await page.getByLabel('Email', { exact: true }).fill(ACCOUNTS[role])
  await page.getByLabel('Password', { exact: true }).fill(DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await expect(page, `${role} should land on the staff workspace after signing in`).toHaveURL(/\/staff$/)
  await expect(page.getByRole('navigation', { name: 'Staff' })).toBeVisible()
  return { role, context, page }
}
