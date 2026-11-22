import { expect, test, type Locator, type Page } from '@playwright/test'
import type { Role } from './support/accounts'
import { signIn, type Session } from './support/signIn'

// The MVP acceptance scenario (proposal §23), run in a real browser against the real API and database. Each step
// is titled with its §23 number. The mapping of steps to criteria, and what each one asserts, is in
// docs/testing/mvp-scenario.md. Seed preconditions are checked where the scenario depends on them, with a message
// naming the precondition. Nothing here is skipped or retried.
//
// It needs a freshly seeded database: the counts in S12 are the whole database's, and a second run on the same data
// finds the stock already used. Both CI and the local commands in the testing doc start from an empty database.

/** The Django admin, where the admin reads the transfer, allocation and audit records (step S12). */
const ADMIN_URL = process.env.E2E_ADMIN_URL ?? 'http://localhost:8000/admin/'

/** Seeded hospitals, in the order the hospitals list shows them (S1). */
const HOSPITALS = ['CityCare General Hospital', 'Seaview Hospital', "Northside Children's Hospital"]
/** Units of O− red cells the nurse asks for at CityCare General (S3). */
const NEED = 3
/** The outcome note for closing the case (S11). Synthetic: it names no patient. */
const OUTCOME = 'Stock held locally and received from Seaview, as planned. Case closed.'

const CASE_URL = /\/staff\/emergencies\/EC-\d{4}-\d{4}$/

test.describe.configure({ mode: 'serial' })

test('MVP acceptance scenario: request, match, reserve, transfer, receipt, history', async ({ browser }) => {
  const people = new Map<Role, Session>()
  /** One signed-in browser context per seeded login, opened the first time a step needs that person. */
  const as = async (role: Role): Promise<Page> => {
    let session = people.get(role)
    if (!session) {
      session = await signIn(browser, role)
      people.set(role, session)
    }
    return session.page
  }

  // Shared between steps: what each step creates and reads.
  let caseRef = ''
  let held = 0
  let short = 0
  let transferId = 0
  let resources: string[] = []

  try {
    await test.step('§23.1 · S1 · Admin sees the three hospitals, all active', async () => {
      const page = await as('admin')
      await page.goto('/staff/hospitals')
      const table = page.getByRole('table', { name: 'Hospitals in the network' })
      await expect(table.locator('tbody tr'), 'Precondition: seed_demo creates three hospitals').toHaveCount(3)
      for (const name of HOSPITALS) {
        await expect(table.getByRole('link', { name, exact: true })).toBeVisible()
      }
      await expect(table.getByText('Active', { exact: true }), 'Precondition: all three hospitals are active').toHaveCount(3)
    })

    await test.step('§23.2 · S2 · Blood bank sees CityCare’s stock and each unit’s status (partial, see docs)', async () => {
      const page = await as('bloodBank')
      await page.goto('/staff/blood')
      const stock = page.getByRole('table', { name: 'Available units by component and group, with each minimum' })
      await expect(stock).toBeVisible()
      const headers = await stock.getByRole('columnheader').allTextContents()
      // Column 0 of the body is the component label (a row header), so the O− column is one less than its header.
      const column = headers.indexOf('O−') - 1
      expect(column, 'Precondition: the stock grid has an O− column').toBeGreaterThanOrEqual(0)
      const redCells = stock.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Red cells', exact: true }) })
      const oNegCount = redCells.getByRole('cell').nth(column).locator('span').first()
      await expect(oNegCount).toHaveText(/^\d+$/)
      expect(Number(await oNegCount.textContent()), 'Precondition: CityCare has O− red cells in stock').toBeGreaterThanOrEqual(1)

      const units = page.getByRole('table', { name: 'Blood units, soonest expiry first' })
      const issued = page.getByRole('group', { name: 'Status' }).getByRole('button', { name: 'Issued', exact: true })
      await issued.click()
      await expect(issued).toHaveAttribute('aria-pressed', 'true')
      await expect(units.locator('tbody tr').first(), 'Precondition: CityCare has issued units to list').toBeVisible()
      const statuses = await units.locator('tbody tr td:nth-child(6)').allTextContents()
      expect(new Set(statuses)).toEqual(new Set(['Issued']))
    })

    await test.step('§23.3 · S3 · Nurse opens a critical request for 3 O− red cells', async () => {
      const page = await as('nurse')
      await page.goto('/staff/emergencies')
      await page.getByRole('button', { name: 'Request blood', exact: true }).click()
      await sendBloodRequest(page, NEED)
      await expect(page, 'the request opens a case and shows it').toHaveURL(CASE_URL)
      caseRef = referenceFrom(page)
      await expect(caseFact(page, 'Status')).toHaveText('Open')
      await expect(page.locator('#case').getByText(`${NEED} × O− red cells`, { exact: true })).toBeVisible()
      await expect(page.locator('#case').getByText('Critical', { exact: true })).toBeVisible()
    })

    await test.step('§23.4, §23.5 · S4 · Local stock is short; the network offers ranked sources', async () => {
      const page = await as('nurse')
      // "Available here: 1 · Short: 2", or "Available here: 4 · Covered locally" when the local stock covers it.
      const local = page.locator('#case').getByText(/^Available here: \d+ · /)
      await expect(local, 'Precondition: the case page shows CityCare’s local stock').toBeVisible()
      const text = (await local.textContent()) ?? ''
      held = Number(/Available here: (\d+)/.exec(text)?.[1])
      expect(held, 'Precondition: CityCare has 1 or 2 usable O− red cells (seed_demo sets exactly 1)').toBeGreaterThanOrEqual(1)
      expect(held, 'Precondition: CityCare has 1 or 2 usable O− red cells (seed_demo sets exactly 1)').toBeLessThanOrEqual(2)
      short = Number(/Short: (\d+)/.exec(text)?.[1] ?? 0)
      expect(short, 'The shortfall is the request less the local stock').toBe(NEED - held)

      const sources = page.locator('#sources')
      await expect(sources.getByRole('heading', { name: `O− red cells: short ${short}`, exact: true })).toBeVisible()
      await expect(sources.getByText('Ordered by earliest expiry first', { exact: true })).toBeVisible()
      const ranked = sources.locator('li').filter({ hasText: /Rank \d+/ })
      await expect(ranked, 'Precondition: two partner hospitals hold O− red cells').toHaveCount(2)
      await expect(ranked.nth(0)).toContainText('Seaview Hospital')
      await expect(ranked.nth(1)).toContainText("Northside Children's Hospital")
      for (const row of [ranked.nth(0), ranked.nth(1)]) {
        await expect(row, 'Precondition: each partner has two available O− red-cell units').toContainText('2 available')
        await expect(row).toContainText('covers it')
      }
      await ranked.nth(0).getByText('Why this score?', { exact: true }).click()
      await expect(ranked.nth(0)).toContainText('Expiry')
      await expect(ranked.nth(0)).toContainText('Distance')
      await expect(ranked.nth(0)).toContainText('points')
    })

    await test.step('§23.6 · S5 · Nurse reserves the local units, and the case starts matching', async () => {
      const page = await as('nurse')
      const reserve = page.getByRole('form', { name: 'Reserve stock here' })
      await expect(reserve.getByLabel('How many')).toHaveValue(String(held))
      await reserve.getByRole('button', { name: `Reserve ${held} here`, exact: true }).click()
      await expect(page.locator('#reservations').getByText('Held', { exact: true })).toHaveCount(held)
      await expect(caseFact(page, 'Status')).toHaveText('Matching')
      await expect(page.locator('#history')).toContainText('Open → Matching')
      await expect(page.locator('#history')).toContainText('System')
    })

    await test.step('§23.6 · S6 · A competing critical case gets none of the held units, and is cancelled', async () => {
      const page = await as('nurse')
      await page.goto('/staff/emergencies')
      await page.getByRole('button', { name: 'Request blood', exact: true }).click()
      await sendBloodRequest(page, 1)
      await expect(page, 'the competing request opens its own case').toHaveURL(CASE_URL)
      expect(referenceFrom(page), 'the competing case is a different case').not.toBe(caseRef)
      await expect(page.locator('#case').getByText(/^Available here: 0 · Short: 1$/)).toBeVisible()
      await expect(page.getByRole('form', { name: 'Reserve stock here' })).toHaveCount(0)
      await page.getByRole('button', { name: 'Cancel case', exact: true }).click()
      await expect(caseFact(page, 'Status')).toHaveText('Cancelled')
    })

    await test.step('§23.7 · S7 · Nurse asks Seaview for the shortfall; the transfer is listed as outgoing', async () => {
      const page = await as('nurse')
      await openCase(page, caseRef)
      const form = page.getByRole('form', { name: 'Request transfer from Seaview Hospital' })
      await expect(form.getByLabel('Quantity'), 'the quantity starts at the shortfall').toHaveValue(String(short))
      await form.getByRole('button', { name: `Request ${short} from Seaview Hospital`, exact: true }).click()
      const notice = page.getByText(/^Transfer #\d+ requested: \d+ from Seaview Hospital\.$/)
      await expect(notice).toBeVisible()
      transferId = Number(/Transfer #(\d+)/.exec((await notice.textContent()) ?? '')?.[1])
      await expect(page.locator('#case-transfers')).toContainText(`Transfer #${transferId}`)
      await expect(page.locator('#case-transfers')).toContainText('Requested')

      await page.goto('/staff/transfers?direction=outgoing')
      const card = page.getByRole('article', { name: `Transfer #${transferId}`, exact: true })
      await expect(card).toContainText(caseRef)
      await expect(card.locator('header')).toContainText('Requested')
    })

    await test.step('§23.8 · S8 · Admin, for Seaview, approves, dispatches and marks the transfer in transit', async () => {
      const page = await as('admin')
      await page.goto('/staff/transfers?direction=outgoing')
      const card = page.getByRole('article', { name: `Transfer #${transferId}`, exact: true })
      await card.getByRole('button', { name: `Approve (transfer #${transferId})`, exact: true }).click()
      await expect(card.locator('header')).toContainText('Approved')
      const set = card.getByRole('listitem').filter({ hasText: 'O− red cells' })
      await expect(set, 'Seaview sets aside one unit per unit asked for').toHaveCount(short)
      resources = await set.allTextContents()

      await card.getByRole('button', { name: `Mark dispatched (transfer #${transferId})`, exact: true }).click()
      await expect(card.locator('header')).toContainText('Dispatched')
      await card.getByRole('button', { name: `Mark in transit (transfer #${transferId})`, exact: true }).click()
      await expect(card.locator('header')).toContainText('In transit')
    })

    await test.step('§23.8, §23.9 · S9 · Blood bank confirms receipt; the units become CityCare’s and the case is part-filled', async () => {
      const page = await as('bloodBank')
      await page.goto('/staff/transfers?direction=outgoing')
      const card = page.getByRole('article', { name: `Transfer #${transferId}`, exact: true })
      const dialogs = armDialog(page)
      await card.getByRole('button', { name: `Confirm receipt (transfer #${transferId})`, exact: true }).click()
      await expect.poll(() => dialogs.length, 'receipt asks for confirmation').toBe(1)
      expect(dialogs[0], 'the confirmation names the case').toContain(caseRef)
      await expect(card.locator('header')).toContainText('Delivered')

      await page.goto('/staff/blood')
      await page.getByRole('group', { name: 'Status' }).getByRole('button', { name: 'Issued', exact: true }).click()
      for (const resource of resources) {
        // A resource reads "O− red cells G7731 26 901010": the donation number is the last three words.
        const number = resource.split(' ').slice(-3).join(' ')
        const row = page.getByRole('row').filter({ has: page.getByRole('cell', { name: number, exact: true }) })
        await expect(row, 'the received unit is on CityCare’s books as issued').toContainText('Issued')
        await expect(row).toContainText('Received from Seaview Hospital')
      }

      await openCase(page, caseRef)
      await expect(caseFact(page, 'Status')).toHaveText('Partially fulfilled')
      await expect(page.locator('#case').getByText(`${short} of ${NEED} allocated · ${held} remaining`, { exact: true })).toBeVisible()
      await expect(page.locator('#case-transfers')).toContainText('Delivered')
    })

    await test.step('§23.9 · S10 · Blood bank allocates the local hold; the case is fulfilled', async () => {
      const page = await as('bloodBank')
      await openCase(page, caseRef)
      const allocate = page.getByRole('button', { name: /^Allocate / })
      await expect(allocate, 'Precondition: only the local hold is left to allocate').toHaveCount(1)
      const dialogs = armDialog(page)
      await allocate.click()
      await expect.poll(() => dialogs.length, 'allocating asks for confirmation').toBe(1)
      expect(dialogs[0], 'the confirmation names the case').toContain(caseRef)
      await expect(caseFact(page, 'Status')).toHaveText('Fulfilled')
      await expect(page.locator('#case').getByText('Fully allocated', { exact: true })).toBeVisible()
      await expect(page.locator('#history')).toContainText('Every need allocated')
    })

    await test.step('§23.10 · S11 · Nurse closes the case with an outcome note', async () => {
      const page = await as('nurse')
      await openCase(page, caseRef)
      await page.getByRole('button', { name: 'Close case', exact: true }).click()
      await page.getByLabel('Outcome note').fill(OUTCOME)
      await page.getByRole('button', { name: 'Close case', exact: true }).click()
      await expect(caseFact(page, 'Status')).toHaveText('Closed')
      await expect(page.locator('#outcome')).toContainText(OUTCOME)
    })

    await test.step('§23.10 · S12 · Doctor reads the case history; admin reads the transfer, allocation and audit records', async () => {
      const doctor = await as('doctor')
      await openCase(doctor, caseRef)
      const history = doctor.locator('#history')
      await expect(history).toContainText('Closed')
      await expect(history).toContainText('Hina Javed')
      await expect(history.getByText(/^Allocated O− red cells .* from Seaview Hospital by Tariq Lodhi$/)).toHaveCount(short)
      await expect(doctor.locator('#case-transfers')).toContainText('Delivered')

      const admin = await as('admin')
      await admin.goto(`${ADMIN_URL}transfers/transfer/`)
      const transferRow = admin.locator('#result_list tbody tr').filter({
        has: admin.getByRole('link', { name: String(transferId), exact: true }),
      })
      await expect(transferRow, 'the admin sees the transfer as delivered').toContainText('Delivered')

      await admin.goto(`${ADMIN_URL}matching/allocation/`)
      const allocations = admin.locator('#result_list tbody tr').filter({ hasText: caseRef })
      await expect(allocations, 'every unit of the need has an allocation record').toHaveCount(NEED)

      await admin.goto(`${ADMIN_URL}audit/auditlog/`)
      const audit = admin.locator('#result_list tbody tr')
      const entry = (action: string) => audit.filter({ hasText: action })
      await expect(entry('transfer.requested').filter({ hasText: 'nurse@demo.citycare.pk' })).toHaveCount(1)
      await expect(entry('transfer.inTransit').filter({ hasText: 'admin@demo.citycare.pk' })).toHaveCount(1)
      await expect(entry('transfer.delivered').filter({ hasText: 'bloodbank@demo.citycare.pk' })).toHaveCount(1)
      await expect(entry('reservation.created'), 'every hold made for the case is audited').toHaveCount(NEED)
      await expect(entry('allocation.created'), 'every allocation is audited').toHaveCount(NEED)
      // The nurse's close of the case, with her email: the move and its actor are both in the row.
      await expect(
        entry('emergencyrequest.status_changed').filter({ hasText: caseRef }).filter({ hasText: 'nurse@demo.citycare.pk' }),
      ).toHaveCount(1)
    })
  } finally {
    await Promise.all([...people.values()].map((session) => session.context.close()))
  }
})

/** The reference of the case the page shows, from its address: /staff/emergencies/EC-2026-0001. */
function referenceFrom(page: Page): string {
  return new URL(page.url()).pathname.split('/').pop() ?? ''
}

/** A fact of the case page: the value next to its label in the case's list. */
function caseFact(page: Page, label: string): Locator {
  return page
    .locator('#case dt')
    .filter({ hasText: new RegExp(`^${label}$`) })
    .locator('xpath=following-sibling::dd[1]')
}

/**
 * Accepts the next browser confirm dialog, and records its message in the returned list. Arm it before the click that
 * opens the dialog: a native confirm blocks that click until it is answered, so it can't be awaited alongside it.
 */
function armDialog(page: Page): string[] {
  const messages: string[] = []
  page.once('dialog', (dialog) => {
    messages.push(dialog.message())
    void dialog.accept()
  })
  return messages
}

/** Opens a case from its reference and waits for its page. */
async function openCase(page: Page, reference: string) {
  await page.goto(`/staff/emergencies/${reference}`)
  await expect(page.locator('#case').getByRole('heading', { name: reference, exact: true })).toBeVisible()
}

/** Fills the "Request blood" form for O− red cells at the given quantity, as Critical, and sends it. */
async function sendBloodRequest(page: Page, quantity: number) {
  await page.getByRole('radio', { name: /^Critical/ }).check()
  await page.getByLabel('Blood group', { exact: true }).selectOption('O-')
  await page.getByLabel('Component', { exact: true }).selectOption('redCells')
  await page.getByLabel('Units', { exact: true }).fill(String(quantity))
  await page.getByRole('button', { name: 'Send request', exact: true }).click()
}
