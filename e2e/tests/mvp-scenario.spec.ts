import { expect, test, type Browser, type Page } from '@playwright/test'

/**
 * Story #57: the MVP acceptance scenario, in a real browser against real servers on `seed_demo` data.
 * CityCare General has a critical case short of O- red cells; the partner hospitals have a few spare units.
 * request → match → transfer request → approve → dispatch by ambulance → en route → arrived → receipt.
 */

const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api'
const PASSWORD = 'CityCare-demo-1'
/** The blood bank login at each partner hospital (seed_demo PARTNER_USERS). */
const SUPPLIER_LOGIN: Record<string, string> = {
  'Seaview Hospital': 'bloodbank.seaview@demo.citycare.pk',
  "Northside Children's Hospital": 'bloodbank.northside@demo.citycare.pk',
}

async function signIn(browser: Browser, email: string): Promise<Page> {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByRole('textbox', { name: 'Password' }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Log in' }).click()
  await page.waitForURL(/\/staff/)
  return page
}

/** A write through the API with the page's session and CSRF cookie, for setup the UI would take many clicks for. */
async function apiPost(page: Page, path: string, body: unknown) {
  const cookies = await page.context().cookies()
  const csrf = cookies.find((c) => c.name === 'csrftoken')?.value ?? ''
  const res = await page.request.post(`${API}${path}`, {
    data: body,
    headers: { 'X-CSRFToken': csrf, Referer: new URL(page.url()).origin },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
  return res.json()
}

test('MVP: a short case gets blood from another hospital by ambulance', async ({ browser }) => {
  // 1. A doctor at CityCare General opens a critical case that needs more O- red cells than the hospital has.
  const doctor = await signIn(browser, 'doctor@demo.citycare.pk')
  const created = await apiPost(doctor, '/emergencies/', {
    severity: 'critical',
    patientRef: 'E2E-01',
    items: [{ type: 'blood', group: 'O-', component: 'redCells', quantity: 20 }],
  })
  const reference: string = created.id

  // 2. The case page shows the shortfall and ranks the other hospitals that have stock.
  await doctor.goto(`/staff/emergencies/${reference}`)
  const sources = doctor.getByRole('region', { name: 'Sources in the network' }).or(doctor.locator('#sources'))
  await expect(sources).toBeVisible()

  // 3. The doctor asks the top-ranked hospital for what it has.
  const ask = doctor.getByRole('button', { name: /^Request \d+ from / }).first()
  const supplierName = (await ask.textContent())!.replace(/^Request \d+ from /, '')
  await ask.click()
  await expect(doctor.getByText(/Transfer #\d+ requested/)).toBeVisible()
  const transferId = Number((await doctor.getByText(/Transfer #\d+ requested/).textContent())!.match(/#(\d+)/)![1])

  // 4. The supplier's blood bank gets a critical alert, approves, and dispatches an ambulance.
  const supplier = await signIn(browser, SUPPLIER_LOGIN[supplierName])
  await expect(supplier.getByRole('alert').filter({ hasText: reference })).toBeVisible()
  await supplier.goto('/staff/transfers')
  await supplier.getByRole('button', { name: `Approve (transfer #${transferId})` }).click()
  await supplier.getByRole('button', { name: 'Dispatch with ambulance' }).click()
  await supplier.getByRole('button', { name: 'Send ambulance' }).click()
  await supplier.getByRole('button', { name: 'Mark en route' }).click()
  await supplier.getByRole('button', { name: 'Mark arrived' }).click()
  await expect(supplier.getByText(/: Arrived/)).toBeVisible()

  // 5. CityCare General's blood bank confirms receipt; the units are allocated to the case.
  const receiver = await signIn(browser, 'bloodbank@demo.citycare.pk')
  receiver.on('dialog', (dialog) => void dialog.accept())  // "Confirm that … has arrived?"
  await receiver.goto('/staff/transfers?direction=outgoing')
  await receiver.getByRole('button', { name: `Confirm receipt (transfer #${transferId})` }).click()
  await expect
    .poll(async () => (await (await receiver.request.get(`${API}/transfers/${transferId}/`)).json()).status, { timeout: 15_000 })
    .toBe('delivered')

  // 6. The case shows what was filled, and the trip is completed.
  const transfer = await (await receiver.request.get(`${API}/transfers/${transferId}/`)).json()
  expect(transfer.status).toBe('delivered')
  expect(transfer.trip.status).toBe('completed')
  const detail = await (await doctor.request.get(`${API}/emergencies/${reference}/`)).json()
  expect(detail.items[0].fulfilled).toBe(transfer.approved)
})
