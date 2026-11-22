import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Donor } from '../../api/donors'
import { at } from '../../test/clock'
import { sampleDonors } from '../../test/fixtures/donors'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

type StaffFetch = ReturnType<typeof mockStaffApi>['fetchMock']

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(at('15:00'))
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status })

/**
 * Answer the first request that matches with `reply` instead of the sample API, then let everything else through.
 * Used for the failures the sample API never gives (a 503, a 403, a clash someone else caused).
 */
function answerOnce(fetchMock: StaffFetch, matches: (url: string, method: string) => boolean, reply: () => Response) {
  const sample = fetchMock.getMockImplementation()!
  let pending = true
  fetchMock.mockImplementation(async (input, init) => {
    const method = (init?.method ?? 'GET').toUpperCase()
    if (pending && matches(String(input), method)) {
      pending = false
      return reply()
    }
    return sample(input, init)
  })
}

const callsTo = (fetchMock: StaffFetch, method: string, path: RegExp) =>
  fetchMock.mock.calls.filter(([url, init]) => (init?.method ?? 'GET').toUpperCase() === method && path.test(String(url)))

const bodyOf = (call: unknown[]) => JSON.parse(String((call[1] as RequestInit).body))

const table = () => screen.findByRole('table', { name: 'Donors' })
const rows = async () => within(await table()).getAllByRole('row').slice(1)
const openDonor = async (name: string) => userEvent.click(await screen.findByRole('button', { name }))
const panel = (code: string) => screen.findByRole('region', { name: `Donor ${code}` })
const slot = (time: string, state: string) => screen.findByRole('button', { name: `${time}, ${state}` })

/** Twenty donors with their own codes, for the 200-row limit. */
function manyDonors(count: number): Donor[] {
  const base = sampleDonors(at('15:00'))[0]
  return Array.from({ length: count }, (_, i) => ({ ...base, id: `DNR-${String(i + 1).padStart(5, '0')}`, fullName: `Sample Donor ${i + 1}` }))
}

describe('DonorsPage: list and search (story #20)', () => {
  it('lists code, name, blood group, last donation and eligibility, and no phone or email', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors')
    const donorRows = await rows()
    expect(donorRows).toHaveLength(6)
    const a = donorRows.find((row) => row.textContent?.includes('Sample Donor A'))!
    expect(a).toHaveTextContent('DNR-00001')
    expect(a).toHaveTextContent('O−')
    expect(a).toHaveTextContent('None yet')
    expect(a).toHaveTextContent('Eligible')
    expect(screen.queryByText('0300 0000001')).toBeNull()
    expect(screen.queryByText('donor-1@example.com')).toBeNull()
  })

  it('searches by name, code or phone after typing pauses, and asks the server for it', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors')
    await rows()
    await userEvent.type(screen.getByLabelText('Search donors'), 'sample donor c')
    await waitFor(() => expect(rows()).resolves.toHaveLength(1))
    expect(await rows()).toHaveLength(1)
    expect(callsTo(fetchMock, 'GET', /blood\/donors\/\?q=sample\+donor\+c$/)).not.toHaveLength(0)

    await userEvent.clear(screen.getByLabelText('Search donors'))
    await userEvent.type(screen.getByLabelText('Search donors'), 'DNR-00004')
    await waitFor(() => expect(rows()).resolves.toHaveLength(1))
    expect(await screen.findByRole('button', { name: 'Sample Donor D' })).toBeInTheDocument()
  })

  it('filters by blood group, with an All groups choice', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors')
    await rows()
    await userEvent.selectOptions(screen.getByLabelText('Blood group'), 'O−')
    await waitFor(() => expect(rows()).resolves.toHaveLength(1))
    expect(callsTo(fetchMock, 'GET', /bloodGroup=O-$/)).not.toHaveLength(0)
    await userEvent.selectOptions(screen.getByLabelText('Blood group'), 'All groups')
    await waitFor(() => expect(rows()).resolves.toHaveLength(6))
  })

  it('says so when there are no donors yet, and when nothing matches', async () => {
    mockStaffApi({ role: 'bloodBank', donors: [] })
    renderStaff('/staff/donors')
    expect(await screen.findByText('No donors registered at your hospital yet.')).toBeInTheDocument()
  })

  it('says so when a search matches nothing', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors')
    await rows()
    await userEvent.type(screen.getByLabelText('Search donors'), 'nobody here')
    expect(await screen.findByText('No donors match this search.')).toBeInTheDocument()
  })

  it('notes when the list is cut at 200 rows', async () => {
    mockStaffApi({ role: 'bloodBank', donors: manyDonors(201) })
    renderStaff('/staff/donors')
    expect(await screen.findByText('Showing the first 200 matches. Narrow the search to see the rest.')).toBeInTheDocument()
    expect(await rows()).toHaveLength(200)
  })

  it('shows a load error with Try again, which loads the list', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    answerOnce(fetchMock, (url) => url.includes('/blood/donors/'), () => json(503, { detail: 'down' }))
    renderStaff('/staff/donors')
    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t load donors.')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await rows()).toHaveLength(6)
  })

  it('opens a donor from the list and keeps the code in the address, so a reload keeps the panel', async () => {
    mockStaffApi({ role: 'bloodBank' })
    const { unmount } = renderStaff('/staff/donors')
    await openDonor('Sample Donor B')
    expect(await panel('DNR-00002')).toBeInTheDocument()
    unmount()

    renderStaff('/staff/donors?donor=DNR-00002')
    expect(await panel('DNR-00002')).toHaveTextContent('Sample Donor B')
  })

  it('shows Donors as the page title', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/donors')
    expect(await screen.findByRole('heading', { level: 1, name: 'Donors' })).toBeInTheDocument()
  })
})

describe('DonorsPage: the donor panel (stories #21 and #22)', () => {
  it('shows eligibility in words and the reason when not eligible', async () => {
    mockStaffApi({ role: 'bloodBank' })
    const { unmount } = renderStaff('/staff/donors?donor=DNR-00003')
    const donor = await panel('DNR-00003')
    expect(within(donor).getByText('Not eligible until 25 Oct 2026')).toBeInTheDocument()
    expect(within(donor).getByText('Low haemoglobin')).toBeInTheDocument()
    expect(within(donor).getByText('Sample Donor C')).toBeInTheDocument()
    unmount()

    renderStaff('/staff/donors?donor=DNR-00004')
    expect(within(await panel('DNR-00004')).getByText('Not eligible, no end date')).toBeInTheDocument()
  })

  it('lists the donor’s units, read only', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors?donor=DNR-00002')
    const units = await within(await panel('DNR-00002')).findByRole('table', { name: 'Units from this donor' })
    expect(within(units).getByText('G7731 26 900201')).toBeInTheDocument()
    expect(within(units).getByText('Expired')).toBeInTheDocument()
  })

  it('shows the phone and email in the panel only', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors?donor=DNR-00001')
    expect(await screen.findByText('donor-1@example.com')).toBeInTheDocument()
    expect(screen.getByText('0300 0000001')).toBeInTheDocument()
  })

  it('shows its own message when the panel fails, and the list stays on screen', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    answerOnce(fetchMock, (url) => url.endsWith('/blood/donors/DNR-00002/'), () => json(503, { detail: 'down' }))
    renderStaff('/staff/donors?donor=DNR-00002')
    expect(await screen.findByText('Couldn’t load this donor. Close it and open the donor again.')).toBeInTheDocument()
    expect(await rows()).toHaveLength(6)
  })

  it('closes the panel, which takes the code out of the address', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors?donor=DNR-00002')
    await panel('DNR-00002')
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Donor DNR-00002' })).toBeNull())
  })
})

describe('DonorsPage: register a donor (story #20)', () => {
  async function openForm() {
    await userEvent.click(await screen.findByRole('button', { name: 'Register a donor' }))
    return within(screen.getByRole('region', { name: 'Register a donor' }))
  }

  it('checks the fields before sending, focuses the first bad one and keeps what was typed', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors')
    const form = await openForm()
    await userEvent.click(form.getByRole('button', { name: 'Register donor' }))
    expect(form.getByText('Enter the donor’s full name')).toBeInTheDocument()
    expect(form.getByText('Choose a blood group')).toBeInTheDocument()
    expect(form.getByLabelText('Full name')).toHaveFocus()
    expect(callsTo(fetchMock, 'POST', /blood\/donors\/$/)).toHaveLength(0)

    await userEvent.type(form.getByLabelText('Full name'), 'Sample Donor Z')
    await userEvent.type(form.getByLabelText(/Phone/), '12')
    await userEvent.type(form.getByLabelText(/Email/), 'not-an-email')
    await userEvent.selectOptions(form.getByLabelText('Blood group'), 'AB−')
    await userEvent.click(form.getByRole('button', { name: 'Register donor' }))
    expect(form.getByLabelText(/Phone/)).toHaveFocus()
    expect(form.getByLabelText(/Phone/)).toHaveAttribute('aria-describedby', expect.stringContaining('donor-phone-error'))
    expect(form.getByLabelText(/Email/)).toHaveAttribute('aria-invalid', 'true')
    expect(form.getByLabelText('Full name')).toHaveValue('Sample Donor Z')
    expect(callsTo(fetchMock, 'POST', /blood\/donors\/$/)).toHaveLength(0)
  })

  it('registers the donor, opens them in the panel and says the code the server set', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors')
    const form = await openForm()
    await userEvent.type(form.getByLabelText('Full name'), 'Sample Donor Z')
    await userEvent.selectOptions(form.getByLabelText('Blood group'), 'AB−')
    await userEvent.type(form.getByLabelText(/Phone/), '0300 0000099')
    await userEvent.click(form.getByRole('button', { name: 'Register donor' }))

    expect(await screen.findByText('Donor DNR-00007 registered.')).toBeInTheDocument()
    expect(await panel('DNR-00007')).toHaveTextContent('Sample Donor Z')
    expect(screen.queryByRole('region', { name: 'Register a donor' })).toBeNull()
    expect(bodyOf(callsTo(fetchMock, 'POST', /blood\/donors\/$/)[0]!)).toEqual({
      fullName: 'Sample Donor Z',
      bloodGroup: 'AB-',
      phone: '0300 0000099',
    })
  })

  it('shows the server’s message under the field for a 400, and the role message for a 403', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    answerOnce(fetchMock, (url, method) => method === 'POST' && url.endsWith('/blood/donors/'), () =>
      json(400, { phone: ['Enter a valid phone number.'] }),
    )
    renderStaff('/staff/donors')
    const form = await openForm()
    await userEvent.type(form.getByLabelText('Full name'), 'Sample Donor Z')
    await userEvent.selectOptions(form.getByLabelText('Blood group'), 'AB−')
    await userEvent.click(form.getByRole('button', { name: 'Register donor' }))
    expect(await form.findByText('Enter a valid phone number.')).toBeInTheDocument()

    answerOnce(fetchMock, (url, method) => method === 'POST' && url.endsWith('/blood/donors/'), () => json(403, { detail: 'no' }))
    await userEvent.click(form.getByRole('button', { name: 'Register donor' }))
    expect(await form.findByText('Your role can’t register donors.')).toBeInTheDocument()
  })
})

describe('DonorsPage: screening (story #21)', () => {
  it('needs a choice, then a reason and an end date (or no end date) before it sends', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors?donor=DNR-00003')
    await panel('DNR-00003')
    await userEvent.click(screen.getByRole('button', { name: 'Save screening' }))
    expect(await screen.findByText('Choose eligible or not eligible')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: 'Not eligible' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save screening' }))
    expect(screen.getByText('Enter the reason. Keep it short and leave out names')).toBeInTheDocument()
    expect(screen.getByLabelText('Reason')).toHaveFocus()

    await userEvent.type(screen.getByLabelText('Reason'), 'Low haemoglobin')
    await userEvent.click(screen.getByRole('button', { name: 'Save screening' }))
    expect(screen.getByText('Choose an end date, or tick No end date')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Deferred until'), { target: { value: '2026-10-01' } })
    await userEvent.click(screen.getByRole('button', { name: 'Save screening' }))
    expect(screen.getByText('The end date must be after today')).toBeInTheDocument()
    expect(callsTo(fetchMock, 'POST', /screening\/$/)).toHaveLength(0)
  })

  it('saves eligible: the panel and the list row update from the server’s answer', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors?donor=DNR-00003')
    const donor = await panel('DNR-00003')
    await userEvent.click(within(donor).getByRole('radio', { name: 'Eligible' }))
    await userEvent.click(within(donor).getByRole('button', { name: 'Save screening' }))
    expect(await within(donor).findByText('Screening saved for DNR-00003: Eligible.')).toBeInTheDocument()
    expect(within(donor).getByText('Eligibility', { selector: 'dt' }).nextElementSibling).toHaveTextContent('Eligible')
    const row = (await rows()).find((r) => r.textContent?.includes('Sample Donor C'))!
    expect(row).toHaveTextContent('Eligible')
  })

  it('saves a permanent deferral with no end date', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors?donor=DNR-00002')
    const donor = await panel('DNR-00002')
    await userEvent.click(within(donor).getByRole('radio', { name: 'Not eligible' }))
    await userEvent.type(within(donor).getByLabelText('Reason'), 'Deferred after a travel screening')
    await userEvent.click(within(donor).getByRole('checkbox', { name: 'No end date (permanent deferral)' }))
    await userEvent.click(within(donor).getByRole('button', { name: 'Save screening' }))
    expect(await within(donor).findByText('Not eligible, no end date')).toBeInTheDocument()
    expect(bodyOf(callsTo(fetchMock, 'POST', /screening\/$/)[0]!)).toEqual({
      eligible: false,
      reason: 'Deferred after a travel screening',
      deferredUntil: null,
    })
  })
})

describe('DonorsPage: booking an appointment (story #22)', () => {
  it('offers 08:00 to 17:00, disables passed and booked times, and books a free one', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors?donor=DNR-00002')
    await panel('DNR-00002')
    expect(await slot('08:00', 'passed')).toBeDisabled()
    expect(await slot('15:30', 'free')).toBeEnabled()
    expect(await slot('17:00', 'free')).toBeEnabled()

    // Tomorrow has a booking for another donor at 10:00 at this hospital.
    fireEvent.change(await screen.findByLabelText('Day'), { target: { value: '2026-10-06' } })
    expect(await slot('10:00', 'booked')).toBeDisabled()
    await userEvent.click(await slot('10:30', 'free'))
    expect(await slot('10:30', 'free')).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Book appointment' }))

    expect(await screen.findByText('Booked DNR-00002 for 6 Oct 2026, 10:30.')).toBeInTheDocument()
    expect(bodyOf(callsTo(fetchMock, 'POST', /appointments\/$/)[0]!)).toEqual({
      donorId: 'DNR-00002',
      startsAt: expect.any(String),
    })
    expect(await screen.findByText('6 Oct 2026, 10:30')).toBeInTheDocument()
  })

  it('shows the donor’s upcoming appointment and disables the book control', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors?donor=DNR-00006')
    await panel('DNR-00006')
    expect(await screen.findByText('This donor already has an appointment on 6 Oct 2026, 10:00. Cancel it to book another.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Book appointment' })).toBeDisabled()
  })

  it('says a permanent deferral cannot be booked, and offers no times', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors?donor=DNR-00004')
    expect(await screen.findByText('This donor can’t be booked.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /, (free|booked|passed)$/ })).toBeNull()
  })

  it('a time someone else took first: the server’s message shows and the bookings reload', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    answerOnce(fetchMock, (url, method) => method === 'POST' && url.endsWith('/blood/appointments/'), () =>
      json(400, { startsAt: ['That slot is already booked.'] }),
    )
    renderStaff('/staff/donors?donor=DNR-00002')
    await panel('DNR-00002')
    fireEvent.change(await screen.findByLabelText('Day'), { target: { value: '2026-10-06' } })
    await userEvent.click(await slot('11:00', 'free'))
    await userEvent.click(screen.getByRole('button', { name: 'Book appointment' }))
    expect(await screen.findByText('That slot is already booked.')).toBeInTheDocument()
    expect(callsTo(fetchMock, 'GET', /blood\/appointments\/$/).length).toBeGreaterThan(1)
  })

  it('cancels after a confirmation, frees the time, and says so', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors?donor=DNR-00006')
    await panel('DNR-00006')
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    await userEvent.click(screen.getByRole('button', { name: 'Keep it' }))
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm cancel' }))
    expect(await screen.findByText('Cancelled the appointment for 6 Oct 2026, 10:00.')).toBeInTheDocument()
    expect(screen.getByText('No upcoming appointments for this donor.')).toBeInTheDocument()

    fireEvent.change(await screen.findByLabelText('Day'), { target: { value: '2026-10-06' } })
    expect(await slot('10:00', 'free')).toBeEnabled()
  })

  it('a cancel the server refuses as already cancelled: its message shows and the list reloads', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank' })
    answerOnce(fetchMock, (url, method) => method === 'POST' && url.endsWith('/appointments/1/cancel/'), () =>
      json(409, { detail: 'This appointment is already cancelled.' }),
    )
    renderStaff('/staff/donors?donor=DNR-00006')
    await panel('DNR-00006')
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm cancel' }))
    expect(await screen.findByText('This appointment is already cancelled.')).toBeInTheDocument()
    expect(callsTo(fetchMock, 'GET', /blood\/appointments\/$/).length).toBeGreaterThan(1)
  })
})
