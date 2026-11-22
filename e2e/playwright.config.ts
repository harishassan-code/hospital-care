import { defineConfig, devices } from '@playwright/test'

// The scenario needs two servers that are already running: the API on http://localhost:8000 and the built
// frontend on http://localhost:5173 (CORS and CSRF accept only that origin by default). This file starts neither.
// docs/testing/mvp-scenario.md has the commands; CI does the same in the `e2e` job.
export default defineConfig({
  testDir: './tests',
  // One scenario in one worker: its steps share the case and the transfer, and run in order.
  fullyParallel: false,
  workers: 1,
  // A failing run is a real signal. A retry would hide a race (docs/aidlc spec, Open question 6).
  retries: 0,
  forbidOnly: !!process.env.CI,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  outputDir: 'test-results',
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
