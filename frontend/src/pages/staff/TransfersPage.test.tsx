import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { sampleTransfers } from '../../test/fixtures/transfers'
import { fail, mockApi, mockStaffApi, sampleAmbulances } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

/** The transfer cards on screen, as "Transfer #N" headings, in the order shown. */
const headings = () => screen.queryAllByRole('article').map((card) => within(card).getByRole('heading').textContent)
const card = async (id: number) => screen.findByRole('article', { name: `Transfer #${id}` })
const posts = (fetchMock: ReturnType<typeof mockStaffApi>['fetchMock']) =>
  fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')
const bodyOf = (call: unknown[]) => JSON.parse(String((call[1] as RequestInit).body))
/** The tab to switch to outgoing transfers. The page takes a moment to load, so it is awaited. */
const outgoingTab = () => screen.findByRole('link', { name: 'Outgoing' })

describe('TransfersPage: incoming and outgoing (story #48)', () => {
  it('lists incoming transfers first, with the active tab marked', async () => {
    mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')

    await card(1)
    expect(headings()).toEqual(['Transfer #1', 'Transfer #2'])
    expect(screen.getByRole('link', { name: 'Incoming' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Outgoing' })).not.toHaveAttribute('aria-current')
  })

  it('switches to outgoing transfers, linking each case to its emergency page', async () => {
    mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await card(1)

    await userEvent.click(await outgoingTab())
    await waitFor(() => expect(headings()).toEqual(['Transfer #4', 'Transfer #3']))
    expect(screen.getByRole('link', { name: 'Outgoing' })).toHaveAttribute('aria-current', 'page')
    const outgoing = await card(4)
    expect(within(outgoing).getByRole('link', { name: 'EC-2026-0002' })).toHaveAttribute('href', '/staff/emergencies/EC-2026-0002')
  })

  it('does not link the case on incoming transfers, which belong to another hospital', async () => {
    mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    const incoming = await card(1)
    expect(within(incoming).queryByRole('link')).toBeNull()
    expect(within(incoming).getByText('EC-2026-0008')).toBeInTheDocument()
  })

  it('filters by status, and asks the server for that status', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await card(1)

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'approved')
    await waitFor(() => expect(headings()).toEqual(['Transfer #2']))
    const requested = fetchMock.mock.calls.map(([url]) => String(url))
    expect(requested.some((url) => url.includes('direction=incoming') && url.includes('status=approved'))).toBe(true)
  })

  it('says so when no transfers are listed, and when the filter matches none', async () => {
    mockStaffApi({ role: 'admin', transfers: [] })
    renderStaff('/staff/transfers')
    expect(await screen.findByText('No transfers yet.')).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'delivered')
    expect(await screen.findByText('No transfers match. Choose another status.')).toBeInTheDocument()
  })

  it('says the system did not answer when the transfers cannot be loaded', async () => {
    mockStaffApi({ role: 'bloodBank', networkDown: true, transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    expect(await screen.findByText(/didn’t respond/)).toBeInTheDocument()
  })

  it('offers confirm receipt only on outgoing transfers, even to an admin who may move any transfer', async () => {
    const inTransit = sampleTransfers(new Date()).find((t) => t.id === 3)!
    // The same in-transit stock, but now CityCare is the supplier, so it is an incoming transfer for the admin's list.
    const incoming = { ...inTransit, id: 9, supplier: { id: 1, name: 'CityCare General Hospital' }, receiver: { id: 2, name: 'Riverside Medical Centre' } }
    mockStaffApi({ role: 'admin', transfers: [incoming] })
    renderStaff('/staff/transfers')
    const onIncoming = await card(9)
    expect(within(onIncoming).getByRole('button', { name: 'Cancel transfer (transfer #9)' })).toBeInTheDocument()
    expect(within(onIncoming).queryByRole('button', { name: 'Confirm receipt (transfer #9)' })).toBeNull()

    await userEvent.click(await outgoingTab())
    expect(within(await card(9)).getByRole('button', { name: 'Confirm receipt (transfer #9)' })).toBeInTheDocument()
  })

  it('shows the requested and approved quantities, and the units set aside', async () => {
    mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await card(1)
    await userEvent.click(await outgoingTab())
    const inTransit = await card(3)
    expect(within(inTransit).getByText('3 requested')).toBeInTheDocument()
    expect(within(inTransit).getByText('3 of 3 approved')).toBeInTheDocument()
    expect(within(inTransit).getByText('O− red cells DN-0101')).toBeInTheDocument()
    expect(within(inTransit).getByText('In transit', { selector: 'span' })).toBeInTheDocument()
  })

  it('shows each change in the history, oldest first, with who made it', async () => {
    mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await userEvent.click(await outgoingTab())
    const inTransit = await card(3)
    await userEvent.click(within(inTransit).getByText('History'))
    const entries = within(inTransit).getAllByRole('listitem').filter((li) => li.querySelector('strong'))
    expect(entries.map((li) => li.querySelector('strong')?.textContent)).toEqual([
      'Requested',
      'Requested → Approved',
      'Approved → Dispatched',
      'Dispatched → In transit',
    ])
    expect(within(entries[3]!).getByText(/Sadia Admin/)).toBeInTheDocument()
    expect(within(entries[3]!).getByText('Van left Riverside')).toBeInTheDocument()
  })
})

describe('TransfersPage: the moves (stories #48, #49)', () => {
  it('approves a request: the card shows the new status, the approved count and the next move, and the page announces it', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')

    const requested = await card(1)
    await userEvent.click(within(requested).getByRole('button', { name: 'Approve (transfer #1)' }))

    expect(await screen.findByText('Transfer #1 is now approved.')).toBeInTheDocument()
    const approved = await card(1)
    expect(within(approved).getByText('1 of 1 approved')).toBeInTheDocument()
    expect(within(approved).getByRole('button', { name: 'Mark dispatched (transfer #1)' })).toBeInTheDocument()
    expect(within(approved).queryByRole('button', { name: 'Approve (transfer #1)' })).toBeNull()
    expect(bodyOf(posts(fetchMock)[0]!)).toEqual({ action: 'approve' })
  })

  it('moves the focus to the card after a move, so keyboard users are not left at the top of the page', async () => {
    mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await userEvent.click(within(await card(1)).getByRole('button', { name: 'Approve (transfer #1)' }))
    await screen.findByText('Transfer #1 is now approved.')
    expect(screen.getByRole('heading', { name: 'Transfer #1' })).toHaveFocus()
  })

  it('dispatches, then marks in transit, one move at a time', async () => {
    mockStaffApi({ role: 'nurse', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')

    // The ventilator transfer is approved and sent by equipment staff, so a nurse may move it. Blood is not theirs.
    await userEvent.click(within(await card(2)).getByRole('button', { name: 'Mark dispatched (transfer #2)' }))
    expect(await screen.findByText('Transfer #2 is now dispatched.')).toBeInTheDocument()
    await userEvent.click(within(await card(2)).getByRole('button', { name: 'Mark in transit (transfer #2)' }))
    expect(await screen.findByText('Transfer #2 is now in transit.')).toBeInTheDocument()
    expect(within(await card(2)).getByText('In transit', { selector: 'span' })).toBeInTheDocument()
  })

  it('shows no buttons on a transfer the role may not move, and says so', async () => {
    mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    const equipment = await card(2)
    expect(within(equipment).queryByRole('button')).toBeNull()
    expect(within(equipment).getByText('No moves for you on this transfer.')).toBeInTheDocument()
  })

  it('rejecting needs a reason: nothing is sent without one, and the reason is sent with the rejection', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')

    await userEvent.click(within(await card(1)).getByRole('button', { name: 'Reject (transfer #1)' }))
    await userEvent.click(screen.getByRole('button', { name: 'Reject request' }))
    expect(screen.getByText('Say why this request is rejected.')).toBeInTheDocument()
    expect(posts(fetchMock)).toHaveLength(0)

    await userEvent.type(screen.getByLabelText('Reason'), 'No platelets to spare this week')
    await userEvent.click(screen.getByRole('button', { name: 'Reject request' }))

    expect(await screen.findByText('Transfer #1 is now rejected.')).toBeInTheDocument()
    const rejected = await card(1)
    expect(within(rejected).getByText('Rejected', { selector: 'span' })).toBeInTheDocument()
    expect(within(rejected).getByText('Reason').nextElementSibling).toHaveTextContent('No platelets to spare this week')
    expect(within(rejected).getByText('None yet')).toBeInTheDocument()
    expect(bodyOf(posts(fetchMock)[0]!)).toEqual({ action: 'reject', reason: 'No platelets to spare this week' })
  })

  it('cancelling asks for an optional reason, and Back returns to the buttons without sending', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await userEvent.click(await outgoingTab())

    await userEvent.click(within(await card(4)).getByRole('button', { name: 'Cancel transfer (transfer #4)' }))
    expect(screen.getByRole('textbox', { name: /Reason/ })).not.toBeRequired()
    await userEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(within(await card(4)).getByRole('button', { name: 'Cancel transfer (transfer #4)' })).toBeInTheDocument()
    expect(posts(fetchMock)).toHaveLength(0)

    await userEvent.click(within(await card(4)).getByRole('button', { name: 'Cancel transfer (transfer #4)' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel transfer' }))
    expect(await screen.findByText('Transfer #4 is now cancelled.')).toBeInTheDocument()
    expect(bodyOf(posts(fetchMock)[0]!)).toEqual({ action: 'cancel' })
  })

  it('confirming receipt asks first, does nothing when declined, and marks the transfer delivered when confirmed', async () => {
    const { fetchMock } = mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await userEvent.click(await outgoingTab())

    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    await userEvent.click(within(await card(3)).getByRole('button', { name: 'Confirm receipt (transfer #3)' }))
    expect(confirm).toHaveBeenCalledOnce()
    expect(posts(fetchMock)).toHaveLength(0)

    confirm.mockReturnValue(true)
    await userEvent.click(within(await card(3)).getByRole('button', { name: 'Confirm receipt (transfer #3)' }))
    expect(await screen.findByText('Transfer #3 is now delivered.')).toBeInTheDocument()
    expect(within(await card(3)).queryByRole('button')).toBeNull()
    expect(bodyOf(posts(fetchMock)[0]!)).toEqual({ action: 'deliver' })
  })
})

describe('TransfersPage: errors', () => {
  it('shows the server’s reason when a move is refused, and re-reads the list', async () => {
    mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    const requested = await card(1)

    // The transfer moved on since this page loaded, so the server refuses the approval the page offers.
    vi.restoreAllMocks()
    const fetchMock = mockApi({
      'GET /transfers/': { body: [] },
      'POST /transfers/:id/actions/': fail(409, { detail: "Can't approve a transfer that is approved." }),
    })
    await userEvent.click(within(requested).getByRole('button', { name: 'Approve (transfer #1)' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("Can't approve a transfer that is approved.")
    // A 409 means the list is out of date, so it is read again.
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url, init]) => String(url).includes('/transfers/?') && (init?.method ?? 'GET') === 'GET')).toBe(true),
    )
  })

  it('shows a plain message when the server fails without saying why', async () => {
    mockStaffApi({ role: 'bloodBank', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    const requested = await card(1)

    vi.restoreAllMocks()
    mockApi({ 'POST /transfers/:id/actions/': fail(500, {}) })
    await userEvent.click(within(requested).getByRole('button', { name: 'Approve (transfer #1)' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The hospital’s system didn’t respond, so nothing changed. Try again.')
  })
})

describe('TransfersPage: access', () => {
  it('blocks a pharmacist, who has no transfers access', async () => {
    mockStaffApi({ role: 'pharmacist', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Incoming' })).toBeNull()
  })

  it('lets an admin see the whole network, not only transfers that touch their hospital', async () => {
    mockStaffApi({ role: 'admin', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await card(1)
    expect(headings()).toEqual(['Transfer #4', 'Transfer #1', 'Transfer #2', 'Transfer #3'])
  })
})

/** The trip panel on a transfer's card (story #51). */
const tripOf = async (id: number) => within(await card(id)).getByRole('region', { name: `Trip for transfer #${id}` })

/** Ask the page to dispatch an ambulance for an approved transfer, choosing the one named. */
async function dispatchFor(id: number, ambulance: string) {
  await userEvent.click(within(await card(id)).getByRole('button', { name: `Dispatch ambulance (transfer #${id})` }))
  await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Ambulance' }), ambulance)
  await userEvent.click(screen.getByRole('button', { name: `Dispatch ambulance (transfer #${id})` }))
}

describe('TransfersPage: dispatching an ambulance (story #51)', () => {
  it('offers dispatch on an approved transfer, lists the available ambulances at the supplier, and sends the one chosen', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')

    await userEvent.click(within(await card(2)).getByRole('button', { name: 'Dispatch ambulance (transfer #2)' }))
    const choice = await screen.findByRole('combobox', { name: 'Ambulance' })
    // Only the supplier's available ambulances: not AMB-02 (in maintenance), AMB-04 (out of service) or the Seaview one.
    expect(within(choice).getAllByRole('option').map((option) => option.textContent)).toEqual([
      'Choose an ambulance',
      'AMB-01 · Advanced life support',
      'AMB-03 · Patient transport',
    ])
    expect(screen.getByText(/about 25 min/)).toBeInTheDocument()

    await userEvent.selectOptions(choice, 'AMB-03 · Patient transport')
    await userEvent.click(screen.getByRole('button', { name: 'Dispatch ambulance (transfer #2)' }))

    expect(await screen.findByText('Ambulance AMB-03 is on its way for transfer #2, about 25 min.')).toBeInTheDocument()
    const dispatch = posts(fetchMock)[0]!
    expect(String(dispatch[0])).toMatch(/\/transfers\/2\/trips\/$/)
    expect(bodyOf(dispatch)).toEqual({ ambulance: 3 })

    const panel = await tripOf(2)
    expect(within(panel).getByRole('heading', { name: 'Ambulance AMB-03' })).toBeInTheDocument()
    expect(within(panel).getByText('about 25 min')).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: 'Mark departed (transfer #2)' })).toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /Mark arrived/ })).toBeNull()
  })

  it('offers no manual move on a transfer while its trip is on the road', async () => {
    mockStaffApi({ role: 'nurse', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await dispatchFor(2, 'AMB-01 · Advanced life support')
    await tripOf(2)

    const transferCard = await card(2)
    expect(within(transferCard).queryByRole('button', { name: /Mark in transit|Cancel transfer|Confirm receipt/ })).toBeNull()
  })

  it('walks the trip: departure puts the transfer in transit, then arrival, then completion frees the ambulance', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await dispatchFor(2, 'AMB-01 · Advanced life support')
    await userEvent.click(within(await tripOf(2)).getByRole('button', { name: 'Mark departed (transfer #2)' }))

    expect(await screen.findByText('Trip for transfer #2 is now en route.')).toBeInTheDocument()
    expect(within(await card(2)).getByText('In transit')).toBeInTheDocument()
    let panel = await tripOf(2)
    expect(within(panel).getByText('En route')).toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: 'Mark departed (transfer #2)' })).toBeNull()

    await userEvent.click(within(panel).getByRole('button', { name: 'Mark arrived (transfer #2)' }))
    expect(await screen.findByText('Trip for transfer #2 is now arrived.')).toBeInTheDocument()
    panel = await tripOf(2)
    await userEvent.click(within(panel).getByRole('button', { name: 'Mark completed (transfer #2)' }))
    expect(await screen.findByText('Trip for transfer #2 is now completed.')).toBeInTheDocument()

    // Completing frees the ambulance but does not deliver the transfer: the receiver confirms it (story #49).
    panel = await tripOf(2)
    expect(within(panel).getByText('Completed', { selector: 'strong' })).toBeInTheDocument()
    expect(within(panel).queryByRole('button')).toBeNull()
    expect(within(await card(2)).getByText('In transit')).toBeInTheDocument()
    expect(posts(fetchMock).map(([url]) => String(url))).toEqual(
      expect.arrayContaining([expect.stringMatching(/\/trips\/\d+\/actions\/$/)]),
    )
  })

  it('says so, with no choice to make, when no ambulance is available at the supplier', async () => {
    const none = sampleAmbulances(new Date()).map((a) => ({ ...a, status: 'maintenance' as const }))
    mockStaffApi({ role: 'nurse', transfers: sampleTransfers(new Date()), ambulances: none })
    renderStaff('/staff/transfers')
    await userEvent.click(within(await card(2)).getByRole('button', { name: 'Dispatch ambulance (transfer #2)' }))
    expect(await screen.findByText('No ambulance is available at CityCare General Hospital right now.')).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Ambulance' })).toBeNull()
  })

  it('asks for an ambulance before sending', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await userEvent.click(within(await card(2)).getByRole('button', { name: 'Dispatch ambulance (transfer #2)' }))
    await screen.findByRole('combobox', { name: 'Ambulance' })
    await userEvent.click(screen.getByRole('button', { name: 'Dispatch ambulance (transfer #2)' }))
    expect(await screen.findByText('Choose an ambulance.')).toBeInTheDocument()
    expect(posts(fetchMock)).toHaveLength(0)
  })

  it('shows the server’s reason when the dispatch is refused, and keeps the choice open', async () => {
    mockStaffApi({ role: 'nurse', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff/transfers')
    await userEvent.click(within(await card(2)).getByRole('button', { name: 'Dispatch ambulance (transfer #2)' }))
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Ambulance' }), 'AMB-01 · Advanced life support')

    // The ambulance was taken since this page loaded, so the server refuses the dispatch.
    vi.restoreAllMocks()
    mockApi({
      'GET /transfers/': { body: sampleTransfers(new Date()) },
      'GET /ambulances/': { body: sampleAmbulances(new Date()) },
      'POST /transfers/:id/trips/': fail(409, { detail: "Can't dispatch a vehicle that is on trip." }),
    })
    await userEvent.click(screen.getByRole('button', { name: 'Dispatch ambulance (transfer #2)' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("Can't dispatch a vehicle that is on trip.")
    expect(screen.getByRole('combobox', { name: 'Ambulance' })).toBeInTheDocument()
  })
})

describe('TransfersPage: the receiving hospital follows the trip', () => {
  it('shows the receiving hospital the trip, read only', async () => {
    // The trip is CityCare's: the receiver is Riverside, so this user sees the trip without any step to take.
    const sent = { ...sampleTransfers(new Date()).find((t) => t.id === 3)!, status: 'inTransit' as const }
    const withTrip = {
      ...sent,
      trip: {
        id: 9,
        transferId: 3,
        status: 'enRoute' as const,
        ambulance: { id: 1, identifier: 'AMB-01', type: 'advanced' },
        etaMinutes: 25,
        dispatchedBy: 'Sadia Admin',
        dispatchedAt: new Date().toISOString(),
        departedAt: new Date().toISOString(),
        arrivedAt: null,
        completedAt: null,
        actions: [],
      },
    }
    mockStaffApi({ role: 'bloodBank', transfers: [withTrip] })
    renderStaff('/staff/transfers')
    await userEvent.click(await outgoingTab())

    const panel = await tripOf(3)
    expect(within(panel).getByRole('heading', { name: 'Ambulance AMB-01' })).toBeInTheDocument()
    expect(within(panel).getByText('En route')).toBeInTheDocument()
    expect(within(panel).queryByRole('button')).toBeNull()
  })
})
