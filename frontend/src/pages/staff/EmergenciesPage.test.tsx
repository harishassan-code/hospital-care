import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { EmergencyCase, Severity } from '../../api/emergencies'
import { fail, mockApi, mockStaffApi, userFor } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

const caseFor = (id: string, severity: Severity): EmergencyCase => ({
  id,
  severity,
  status: 'open',
  patientRef: '',
  hospital: null,
  createdBy: 'Hina Javed',
  createdAt: new Date().toISOString(),
  items: [{ type: 'bed', bedType: 'icu', quantity: 1 }],
})

const table = () => screen.findByRole('table', { name: 'Emergency cases, most severe first, then oldest first' })
const references = async () =>
  within(await table())
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('cell')[0].textContent)

async function openForm() {
  await userEvent.click(await screen.findByRole('button', { name: 'New case' }))
  return screen.getByRole('region', { name: 'New emergency case' })
}

const next = () => userEvent.click(screen.getByRole('button', { name: 'Next' }))

describe('EmergenciesPage (stories #30 create case, #32 requirements)', () => {
  it('lists the hospital’s cases with what they need', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/emergencies')
    expect(await references()).toEqual(['EC-2026-0002Bay 4', 'EC-2026-0001'])
    const row = (await table()).querySelectorAll('tbody tr')[0] as HTMLElement
    expect(within(row).getByText('Critical')).toBeInTheDocument()
    expect(within(row).getByText('4 × O− red cells, 1 × ICU bed')).toBeInTheDocument()
    expect(within(row).getByText('Open')).toBeInTheDocument()
  })

  it('links each case reference to its page (story #34)', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/emergencies')
    const link = within(await table()).getByRole('link', { name: 'EC-2026-0002' })
    expect(link).toHaveAttribute('href', '/staff/emergencies/EC-2026-0002')

    await userEvent.click(link)
    expect(await screen.findByRole('heading', { name: 'EC-2026-0002' })).toBeInTheDocument()
    expect(await screen.findByRole('region', { name: 'Status history' })).toBeInTheDocument()
  })

  it('labels an escalated case in words in the list (story #35)', async () => {
    mockStaffApi({ role: 'nurse', cases: [{ ...caseFor('EC-2026-0001', 'critical'), status: 'escalated' }, caseFor('EC-2026-0002', 'high')] })
    renderStaff('/staff/emergencies')

    const rows = within(await table()).getAllByRole('row').slice(1)
    expect(within(rows[0]!).getByText('Escalated')).toBeInTheDocument()
    expect(within(rows[1]!).queryByText('Escalated')).toBeNull()
    expect(within(rows[1]!).getByText('Open')).toBeInTheDocument()
  })

  it('shows cases in the order the server sends them, without re-sorting (#31)', async () => {
    // Deliberately not severity order: the page shows what it is given.
    mockStaffApi({ role: 'nurse', cases: [caseFor('EC-2026-0004', 'low'), caseFor('EC-2026-0001', 'critical'), caseFor('EC-2026-0003', 'moderate')] })
    renderStaff('/staff/emergencies')
    expect(await references()).toEqual(['EC-2026-0004', 'EC-2026-0001', 'EC-2026-0003'])
  })

  it('marks a critical case with its label, and gives every level its own label (#31)', async () => {
    mockStaffApi({ role: 'nurse', cases: [caseFor('EC-2026-0001', 'critical'), caseFor('EC-2026-0002', 'high'), caseFor('EC-2026-0003', 'moderate'), caseFor('EC-2026-0004', 'low')] })
    renderStaff('/staff/emergencies')
    const rows = within(await table()).getAllByRole('row').slice(1)
    const labels = rows.map((row) => within(row).getAllByRole('cell')[1].textContent)
    expect(labels).toEqual(['Critical', 'High', 'Moderate', 'Low'])
    expect(within(rows[0]).getByText('Critical')).toBeInTheDocument()
    expect(within(rows[1]).queryByText('Critical')).toBeNull()
  })

  it('lets doctors, nurses and admins open cases, but not other staff', async () => {
    for (const role of ['doctor', 'nurse', 'admin'] as const) {
      mockStaffApi({ role })
      const { unmount } = renderStaff('/staff/emergencies')
      expect(await screen.findByRole('button', { name: 'New case' })).toBeInTheDocument()
      unmount()
      vi.restoreAllMocks()
    }
    for (const role of ['bloodBank', 'pharmacist'] as const) {
      mockStaffApi({ role })
      const { unmount } = renderStaff('/staff/emergencies')
      await table()
      expect(screen.queryByRole('button', { name: 'New case' })).toBeNull()
      unmount()
      vi.restoreAllMocks()
    }
  })

  it('opens a case in three steps without any patient data', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/emergencies')
    const form = await openForm()

    expect(within(form).getByRole('heading', { name: 'Step 1 of 3: Case' })).toHaveFocus()
    await userEvent.click(within(form).getByRole('radio', { name: /Critical/ }))
    await next()

    expect(within(form).getByRole('heading', { name: 'Step 2 of 3: What’s needed' })).toHaveFocus()
    await userEvent.selectOptions(within(form).getByLabelText('Blood group'), 'O-')
    await userEvent.clear(within(form).getByLabelText('Units'))
    await userEvent.type(within(form).getByLabelText('Units'), '4')
    await userEvent.click(within(form).getByRole('button', { name: 'Add another need' }))
    const second = within(form).getByRole('group', { name: 'Need 2' })
    await userEvent.selectOptions(within(second).getByLabelText('Type'), 'bed')
    await userEvent.selectOptions(within(second).getByLabelText('Bed type'), 'icu')
    await next()

    expect(within(form).getByRole('heading', { name: 'Step 3 of 3: Review' })).toHaveFocus()
    expect(within(form).getByText('4 × O− red cells')).toBeInTheDocument()
    expect(within(form).getByText('1 × ICU bed')).toBeInTheDocument()
    expect(within(form).getByText('None')).toBeInTheDocument()
    await userEvent.click(within(form).getByRole('button', { name: 'Open case' }))

    expect(await screen.findByText('Case EC-2026-0003 is open.')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'New emergency case' })).toBeNull()
    expect(screen.getByRole('button', { name: 'New case' })).toHaveFocus()
    // The new critical case sorts after the older critical one: the list is reloaded from the server.
    await waitFor(async () => expect(await references()).toEqual(['EC-2026-0002Bay 4', 'EC-2026-0003', 'EC-2026-0001']))
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(JSON.parse(String(post[1]!.body))).toEqual({
      severity: 'critical',
      patientRef: '',
      items: [
        { type: 'blood', group: 'O-', component: 'redCells', quantity: 4 },
        { type: 'bed', bedType: 'icu', quantity: 1 },
      ],
    })
  })

  it('opens a case with equipment and an operating room, and says each the way staff do (#32)', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/emergencies')
    const form = await openForm()
    await userEvent.click(within(form).getByRole('radio', { name: /High/ }))
    await next()

    const first = within(form).getByRole('group', { name: 'Need 1' })
    await userEvent.selectOptions(within(first).getByLabelText('Type'), 'equipment')
    await userEvent.selectOptions(within(first).getByLabelText('Equipment'), 'ventilator')
    await userEvent.clear(within(first).getByLabelText('Pieces'))
    await userEvent.type(within(first).getByLabelText('Pieces'), '2')
    await userEvent.click(within(form).getByRole('button', { name: 'Add another need' }))
    const second = within(form).getByRole('group', { name: 'Need 2' })
    await userEvent.selectOptions(within(second).getByLabelText('Type'), 'operatingRoom')
    await userEvent.selectOptions(within(second).getByLabelText('Capability'), 'cardiac')
    await next()

    expect(within(form).getByText('2 × Ventilator')).toBeInTheDocument()
    expect(within(form).getByText('1 × Operating room (cardiac)')).toBeInTheDocument()
    await userEvent.click(within(form).getByRole('button', { name: 'Open case' }))

    expect(await screen.findByText('Case EC-2026-0003 is open.')).toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(JSON.parse(String(post[1]!.body)).items).toEqual([
      { type: 'equipment', equipmentType: 'ventilator', quantity: 2 },
      { type: 'operatingRoom', capability: 'cardiac', quantity: 1 },
    ])
  })

  it('shows a server refusal of an operating room’s capability on that field', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/emergencies')
    const form = await openForm()
    await userEvent.click(within(form).getByRole('radio', { name: /High/ }))
    await next()
    await userEvent.selectOptions(within(form).getByLabelText('Type'), 'operatingRoom')
    await next()
    vi.restoreAllMocks()
    mockApi({
      'GET /auth/me/': { body: userFor('doctor') },
      'POST /emergencies/': fail(400, { items: { '0': { capability: ['Choose one of the listed capabilities.'] } } }),
    })
    await userEvent.click(within(form).getByRole('button', { name: 'Open case' }))

    expect(await within(form).findByText('Choose one of the listed capabilities.')).toBeInTheDocument()
    expect(within(form).getByLabelText('Capability')).toHaveAccessibleDescription('Choose one of the listed capabilities.')
    expect(within(form).getByRole('heading', { name: 'Step 2 of 3: What’s needed' })).toBeInTheDocument()
  })

  it('offers the four severity levels, most severe first (#31)', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/emergencies')
    const form = await openForm()
    const levels = within(form)
      .getAllByRole('radio')
      .map((radio) => radio.closest('label')?.querySelector('strong')?.textContent)
    expect(levels).toEqual(['Critical', 'High', 'Moderate', 'Low'])
  })

  it('won’t move on until each step is valid', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/emergencies')
    const form = await openForm()

    await next()
    expect(within(form).getByText('Choose how severe the case is')).toBeInTheDocument()
    expect(within(form).getByRole('heading', { name: 'Step 1 of 3: Case' })).toBeInTheDocument()
    await userEvent.click(within(form).getByRole('radio', { name: /High/ }))
    await next()

    const units = within(form).getByLabelText('Units')
    await userEvent.clear(units)
    await userEvent.type(units, '25')
    await next()
    expect(within(form).getByText('At most 20 per line; add another line for more')).toBeInTheDocument()
    expect(units).toHaveFocus()

    await userEvent.click(within(form).getByRole('button', { name: 'Back' }))
    expect(within(form).getByRole('radio', { name: /High/ })).toBeChecked()
  })

  it('shows what went wrong when the server refuses the case', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/emergencies')
    const form = await openForm()
    await userEvent.click(within(form).getByRole('radio', { name: /Moderate/ }))
    await next()
    await next()

    vi.restoreAllMocks()
    mockApi({
      'GET /auth/me/': { body: userFor('doctor') },
      'POST /emergencies/': fail(400, { items: { '0': { quantity: ['Ask for at most 20 per item.'] } } }),
    })
    await userEvent.click(within(form).getByRole('button', { name: 'Open case' }))
    expect(await within(form).findByText('Ask for at most 20 per item.')).toBeInTheDocument()
    expect(within(form).getByRole('heading', { name: 'Step 2 of 3: What’s needed' })).toBeInTheDocument()

    vi.restoreAllMocks()
    mockApi({ 'POST /emergencies/': fail(503) })
    await next()
    await userEvent.click(within(form).getByRole('button', { name: 'Open case' }))
    expect(await within(form).findByText('The hospital’s system didn’t respond, so the case wasn’t opened. Try again.')).toBeInTheDocument()
  })

  it('says so when there are no cases, and is closed to patients', async () => {
    mockStaffApi({ role: 'pharmacist', cases: [] })
    const { unmount } = renderStaff('/staff/emergencies')
    expect(await screen.findByText('No emergency cases yet.')).toBeInTheDocument()
    unmount()
    vi.restoreAllMocks()
    mockStaffApi({ role: 'patient' })
    renderStaff('/staff/emergencies')
    expect(await screen.findByRole('heading', { name: 'This area is for hospital staff' })).toBeInTheDocument()
  })
})

const quickForm = async () => {
  await userEvent.click(await screen.findByRole('button', { name: 'Request blood' }))
  return screen.getByRole('region', { name: 'Request blood' })
}
const sendRequest = (form: HTMLElement) => userEvent.click(within(form).getByRole('button', { name: 'Send request' }))

describe('EmergenciesPage quick blood request (story #36)', () => {
  it('sends one blood need with its urgency, then opens the new case', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/emergencies')
    const form = await quickForm()

    await userEvent.click(within(form).getByRole('radio', { name: /Critical/ }))
    await userEvent.selectOptions(within(form).getByLabelText('Blood group'), 'AB-')
    await userEvent.selectOptions(within(form).getByLabelText('Component'), 'platelets')
    const units = within(form).getByLabelText('Units')
    expect(units).toHaveAttribute('type', 'number')
    expect(units).toHaveAttribute('min', '1')
    await userEvent.clear(units)
    await userEvent.type(units, '3')
    await sendRequest(form)

    const reference = `EC-${new Date().getFullYear()}-0003`
    expect(await screen.findByRole('heading', { name: reference })).toBeInTheDocument()
    const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(posts).toHaveLength(1)
    expect(JSON.parse(String(posts[0]![1]!.body))).toEqual({
      severity: 'critical',
      patientRef: '',
      items: [{ type: 'blood', group: 'AB-', component: 'platelets', quantity: 3 }],
    })
  })

  it('won’t send until urgency is chosen and the units are a whole number from 1 to 20', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/emergencies')
    const form = await quickForm()

    await sendRequest(form)
    expect(within(form).getByText('Choose how urgent the request is')).toBeInTheDocument()
    expect(within(form).getByRole('alert')).toHaveTextContent('The request wasn’t sent. Fix the fields marked below.')
    await userEvent.click(within(form).getByRole('radio', { name: /High/ }))

    const units = within(form).getByLabelText('Units')
    for (const [typed, message] of [
      ['0', 'Enter a whole number of 1 or more'],
      ['2.5', 'Enter a whole number of 1 or more'],
      ['21', 'At most 20 units per request; send another request for more'],
    ] as const) {
      await userEvent.clear(units)
      await userEvent.type(units, typed)
      await sendRequest(form)
      expect(within(form).getByText(message)).toBeInTheDocument()
    }
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('shows the server’s error on the field it belongs to', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/emergencies')
    const form = await quickForm()
    await userEvent.click(within(form).getByRole('radio', { name: /Moderate/ }))

    vi.restoreAllMocks()
    mockApi({
      'GET /auth/me/': { body: userFor('doctor') },
      'POST /emergencies/': fail(400, { items: { '0': { component: ['"bogus" is not a valid choice.'] } } }),
    })
    await sendRequest(form)

    expect(await within(form).findByText('"bogus" is not a valid choice.')).toBeInTheDocument()
    expect(within(form).getByLabelText('Component')).toHaveAccessibleDescription('"bogus" is not a valid choice.')
    expect(within(form).getByRole('alert')).toHaveTextContent('The request wasn’t sent. Fix the fields marked below.')
  })

  it('says so when the hospital’s system is down, and keeps the form for another try', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/emergencies')
    const form = await quickForm()
    await userEvent.click(within(form).getByRole('radio', { name: /Low/ }))

    vi.restoreAllMocks()
    mockApi({ 'POST /emergencies/': fail(503) })
    await sendRequest(form)

    expect(await within(form).findByText('The hospital’s system didn’t respond, so the request wasn’t sent. Try again.')).toBeInTheDocument()
    expect(within(form).getByRole('button', { name: 'Send request' })).toBeEnabled()
  })

  it('is offered to roles that can edit emergencies, beside “New case”', async () => {
    for (const role of ['admin', 'doctor', 'nurse'] as const) {
      mockStaffApi({ role })
      const { unmount } = renderStaff('/staff/emergencies')
      expect(await screen.findByRole('button', { name: 'Request blood' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'New case' })).toBeInTheDocument()
      unmount()
      vi.restoreAllMocks()
    }
  })

  it('is not offered to view-only roles, who still see the network feed link', async () => {
    for (const role of ['bloodBank', 'pharmacist'] as const) {
      mockStaffApi({ role })
      const { unmount } = renderStaff('/staff/emergencies')
      await table()
      expect(screen.queryByRole('button', { name: 'Request blood' })).toBeNull()
      expect(screen.getByRole('link', { name: 'Network requests' })).toHaveAttribute('href', '/staff/emergencies/feed')
      unmount()
      vi.restoreAllMocks()
    }
  })
})
