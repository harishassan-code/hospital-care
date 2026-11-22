import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { at } from '../../test/clock'
import { sampleTransfers } from '../../test/fixtures/transfers'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(at('15:00'))
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

/** The link targets of the status tiles, in the order they are shown. */
const tileLinks = (tiles: HTMLElement) => within(tiles).getAllByRole('link').map((a) => a.getAttribute('href'))

describe('OverviewPage', () => {
  it('summarises every module in a linked tile', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    expect(tileLinks(tiles)).toEqual(['/staff/beds', '/#emergency', '/staff/emergencies', '/staff/transfers', '/staff/blood', '/staff/pharmacy'])
    expect(within(tiles).getByText(/of 106 beds/)).toBeInTheDocument()
    expect(within(tiles).getByText('7')).toBeInTheDocument()
    expect(within(tiles).getByText('About 24 min wait')).toBeInTheDocument()
  })

  it('still works when the live ER status can’t be loaded', async () => {
    mockStaffApi({ role: 'admin', erDown: true })
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    expect(within(tiles).getByText('Live status unavailable')).toBeInTheDocument()
    expect(within(tiles).getByText(/of 106 beds/)).toBeInTheDocument()
  })

  it('lists what needs attention, critical first, with links', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    const panel = await screen.findByRole('region', { name: 'Needs attention' })
    const items = within(panel).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Critical')
    expect(within(panel).getByText(/Insulin glargine/)).toBeInTheDocument()
    expect(within(panel).getByText(/O− red cells/)).toBeInTheDocument()
  })

  it('charts bed occupancy by ward and red-cell stock by group', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    const beds = await screen.findByRole('region', { name: 'Bed occupancy by ward' })
    expect(within(within(beds).getByRole('list', { name: 'Wards' })).getAllByRole('listitem')).toHaveLength(7)
    const blood = screen.getByRole('region', { name: 'Red-cell stock by group' })
    expect(within(within(blood).getByRole('list', { name: 'Blood groups' })).getAllByRole('listitem')).toHaveLength(8)
  })

  it('only shows what the role may see', async () => {
    mockStaffApi({ role: 'pharmacist' })
    renderStaff('/staff')
    await screen.findByRole('region', { name: 'Needs attention' })
    expect(screen.queryByRole('region', { name: 'Bed occupancy by ward' })).toBeNull()
    expect(screen.queryByText(/O− red cells/)).toBeNull()
    expect(screen.getByText(/Insulin glargine/)).toBeInTheDocument()
  })

  it.each([
    ['admin', ['/staff/beds', '/#emergency', '/staff/emergencies', '/staff/transfers', '/staff/blood', '/staff/pharmacy']],
    ['doctor', ['/staff/beds', '/#emergency', '/staff/emergencies', '/staff/transfers', '/staff/blood', '/staff/pharmacy']],
    ['nurse', ['/staff/beds', '/#emergency', '/staff/emergencies', '/staff/transfers', '/staff/pharmacy']],
    ['bloodBank', ['/#emergency', '/staff/emergencies', '/staff/transfers', '/staff/blood']],
    ['pharmacist', ['/#emergency', '/staff/emergencies', '/staff/pharmacy']],
  ] as const)('shows the tiles the %s role may see, with the two request tiles in place', async (role, links) => {
    mockStaffApi({ role })
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    expect(tileLinks(tiles)).toEqual(links)
  })

  it('shows open cases, and the critical count in words', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    const requests = within(tiles).getByRole('link', { name: /Open requests/ })
    expect(requests).toHaveAttribute('href', '/staff/emergencies')
    expect(requests).toHaveTextContent('2 open cases')
    expect(requests).toHaveTextContent('1 critical')
  })

  it('says none critical when no open case is critical', async () => {
    const now = new Date()
    mockStaffApi({
      role: 'doctor',
      cases: [
        {
          id: 'EC-2026-0001',
          severity: 'moderate',
          status: 'open',
          patientRef: '',
          hospital: { id: 1, name: 'CityCare General Hospital' },
          createdBy: 'Hina Javed',
          createdAt: now.toISOString(),
          items: [{ type: 'bed', bedType: 'general', quantity: 2 }],
        },
      ],
    })
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    const requests = within(tiles).getByRole('link', { name: /Open requests/ })
    expect(requests).toHaveTextContent('1 open case')
    expect(requests).toHaveTextContent('None critical')
  })

  it('shows pending transfers, what is to answer and what is outgoing, for a doctor at CityCare', async () => {
    mockStaffApi({ role: 'doctor', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    const transfers = within(tiles).getByRole('link', { name: /Transfers/ })
    expect(transfers).toHaveAttribute('href', '/staff/transfers')
    expect(transfers).toHaveTextContent('4 pending transfers')
    expect(transfers).toHaveTextContent('1 to answer · 2 outgoing')
    expect(transfers).toHaveTextContent('1 waiting for an answer')
  })

  it('says nothing to answer when no incoming request is waiting', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    const transfers = within(tiles).getByRole('link', { name: /Transfers/ })
    expect(transfers).toHaveTextContent('0 pending transfers')
    expect(transfers).toHaveTextContent('0 to answer · 0 outgoing')
    expect(transfers).toHaveTextContent('Nothing to answer')
  })

  it('counts an admin’s network transfers once each', async () => {
    mockStaffApi({ role: 'admin', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    const transfers = within(tiles).getByRole('link', { name: /Transfers/ })
    expect(transfers).toHaveTextContent('4 pending transfers')
    expect(transfers).not.toHaveTextContent('8 pending')
  })

  it('does not show the Transfers tile to a pharmacist, and does not ask for transfers', async () => {
    const { fetchMock } = mockStaffApi({ role: 'pharmacist', transfers: sampleTransfers(new Date()) })
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    expect(within(tiles).queryByRole('link', { name: /Transfers/ })).toBeNull()
    expect(within(tiles).queryByText(/to answer/)).toBeNull()
    const paths = fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname)
    expect(paths).not.toContain('/api/transfers/')
  })

  it('shows Unavailable for the Transfers tile when transfers fail, and the other tiles still show', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    const answer = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input, init) =>
      new URL(String(input)).pathname === '/api/transfers/' ? Promise.resolve(new Response('{}', { status: 500 })) : answer(input, init),
    )
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    const transfers = within(tiles).getByRole('link', { name: /Transfers/ })
    expect(transfers).toHaveAttribute('href', '/staff/transfers')
    expect(transfers).toHaveTextContent('Unavailable')
    expect(transfers).toHaveTextContent('Check the Transfers page')
    expect(within(tiles).getByText(/of 106 beds/)).toBeInTheDocument()
    expect(within(tiles).getByRole('link', { name: /Open requests/ })).toHaveTextContent('2 open cases')
  })

  it('shows Unavailable for Open requests when the cases fail, and the other tiles still show', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor', transfers: sampleTransfers(new Date()) })
    const answer = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input, init) =>
      new URL(String(input)).pathname === '/api/emergencies/' ? Promise.resolve(new Response('{}', { status: 500 })) : answer(input, init),
    )
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    const requests = within(tiles).getByRole('link', { name: /Open requests/ })
    expect(requests).toHaveAttribute('href', '/staff/emergencies')
    expect(requests).toHaveTextContent('Unavailable')
    expect(requests).toHaveTextContent('Check the Emergencies page')
    expect(within(tiles).getByRole('link', { name: /Transfers/ })).toHaveTextContent('4 pending transfers')
  })

  it('says when the figures were last updated', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    expect(await screen.findByText('Updated 15:00')).toBeInTheDocument()
  })
})
