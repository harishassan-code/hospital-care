import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CommandCentre } from '../../api/commandCentre'
import { at } from '../../test/clock'
import { networkTotals, sampleCommandCentre } from '../../test/fixtures/commandCentre'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

const NOW = at('15:00')

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOW)
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  delete (document as { visibilityState?: unknown }).visibilityState
})

const board = () => screen.findByRole('table', { name: /Network figures/ })

function setVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
  document.dispatchEvent(new Event('visibilitychange'))
}

/** Make the command centre call fail while `down` is true, and pass every other call through to the mock. */
function outage(fetchMock: ReturnType<typeof mockStaffApi>['fetchMock']) {
  const working = fetchMock.getMockImplementation()!
  const state = { down: false }
  fetchMock.mockImplementation((input, init) =>
    state.down && String(input).endsWith('/command-centre/')
      ? Promise.resolve(new Response('{}', { status: 503 }))
      : working(input, init),
  )
  return state
}

describe('City command centre page', () => {
  it('shows the network in one table, one column per hospital and one for the network', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/command-centre')
    const table = await board()
    const headers = within(table.querySelector('thead') as HTMLElement)
      .getAllByRole('columnheader')
      .map((th) => th.textContent)
    expect(headers).toEqual(['Measure', 'CityCare General Hospital', 'Old Town Blood Centre', 'Seaview Hospital', 'All hospitals'])
  })

  it('writes each shortage out in words, with the count and the minimum', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/command-centre')
    await board()
    expect(screen.getByText('Critical: 1 unit, minimum 4')).toBeInTheDocument()
    expect(screen.getByText('Low: 22 units, minimum 30')).toBeInTheDocument()
  })

  it('summarises the shortages above the table, group by group', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/command-centre')
    const summary = await screen.findByRole('region', { name: 'Shortages' })
    const items = within(summary)
      .getAllByRole('listitem')
      .map((li) => li.textContent)
    expect(items).toEqual([
      'O− red cells: 1 hospital critical',
      'O+ red cells: 1 hospital low',
      'A− red cells: 1 hospital critical',
      'B+ red cells: 1 hospital critical',
      'AB− red cells: 1 hospital low',
    ])
  })

  it('says "No shortages" in words for each hospital without one', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/command-centre')
    await board()
    expect(screen.getAllByText('No shortages')).toHaveLength(2)
    expect(screen.getByText('Short: O− critical, O+ low, A− critical, B+ critical, AB− low')).toBeInTheDocument()
  })

  it('says how many units are near expiry at each hospital, and across the network', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/command-centre')
    await board()
    expect(screen.getAllByText('6 units expire within 3 days')).toHaveLength(1)
    // Plasma and platelets at CityCare, and the same two in the network column.
    expect(screen.getAllByText('2 units expire within 3 days')).toHaveLength(4)
    expect(screen.getByText('14 units expire within 3 days across the network.')).toBeInTheDocument()
  })

  it('shows when the figures were taken and says they refresh every minute', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/command-centre')
    await board()
    expect(screen.getByText(/Figures as of 15:00\. They refresh every minute/)).toBeInTheDocument()
  })

  it('has no button that changes anything', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/command-centre')
    const table = await board()
    expect(within(table).queryAllByRole('button')).toHaveLength(0)
    expect(within(table).queryAllByRole('link')).toHaveLength(0)
  })

  it('says so when the network has no active hospital', async () => {
    const empty: CommandCentre = {
      updatedAt: NOW.toISOString(),
      nearExpiryDays: 3,
      totals: networkTotals([]),
      hospitals: [],
    }
    mockStaffApi({ role: 'admin', commandCentre: empty })
    renderStaff('/staff/command-centre')
    expect(await screen.findByText('There are no active hospitals in the network yet.')).toBeInTheDocument()
    expect(screen.getByText('No blood group is short at any hospital.')).toBeInTheDocument()
  })

  it('shows an error with a way to try again when the figures cannot load at first', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    const state = outage(fetchMock)
    state.down = true
    renderStaff('/staff/command-centre')
    expect(await screen.findByRole('alert')).toHaveTextContent('The network’s figures couldn’t be loaded.')

    state.down = false
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await board()).toBeInTheDocument()
  })

  it('keeps the last figures and warns that they may be out of date when a refresh fails', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    const state = outage(fetchMock)
    renderStaff('/staff/command-centre')
    await board()

    state.down = true
    setVisibility('hidden')
    setVisibility('visible')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The figures may be out of date.')
    expect(screen.getByText('Critical: 1 unit, minimum 4')).toBeInTheDocument()
    expect(screen.getByRole('table', { name: /Network figures/ })).toBeInTheDocument()

    state.down = false
    setVisibility('hidden')
    setVisibility('visible')
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })

  it('is not shown to other roles, and the API refuses them too', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/command-centre')
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
  })

  it('lists the beds, equipment, rooms and emergencies the figures carry', async () => {
    mockStaffApi({ role: 'admin', commandCentre: sampleCommandCentre(NOW) })
    renderStaff('/staff/command-centre')
    const table = await board()
    const labels = within(table)
      .getAllByRole('rowheader')
      .map((th) => th.textContent)
    expect(labels).toEqual(
      expect.arrayContaining(['ICU', 'Ventilators', 'Available', 'Active cases', 'Open needs: Blood', 'Open needs: Operating rooms']),
    )
  })
})
