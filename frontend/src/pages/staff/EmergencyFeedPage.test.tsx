import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { sampleCases } from '../../test/fixtures/emergencies'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

const FEED = '/staff/emergencies/feed'
const list = async (name: 'Blood requests' | 'Bed requests') => screen.findByRole('list', { name })
const entries = async (name: 'Blood requests' | 'Bed requests') => within(await list(name)).getAllByRole('listitem')
const references = async (name: 'Blood requests' | 'Bed requests') =>
  (await entries(name)).map((li) => li.querySelector('strong')?.nextElementSibling?.textContent)

describe('EmergencyFeedPage (story #36 network requests)', () => {
  it('lists blood requests from every hospital in the server’s order, with severity, status and needs', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(FEED)

    const [first, second, third] = await entries('Blood requests')
    expect(await references('Blood requests')).toEqual(['EC-2026-0007', 'EC-2026-0002', 'EC-2026-0008'])
    expect(within(first!).getByText('Riverside Medical Centre')).toBeInTheDocument()
    expect(within(first!).getByText('Critical')).toBeInTheDocument()
    expect(within(first!).getByText('Matching')).toBeInTheDocument()
    expect(within(first!).getByText('6 × O− red cells (2 filled)')).toBeInTheDocument()
    expect(within(second!).getByText('CityCare General Hospital')).toBeInTheDocument()
    expect(within(second!).getByText('4 × O− red cells')).toBeInTheDocument()
    expect(within(third!).getByText('High')).toBeInTheDocument()
    expect(within(third!).getByText('Escalated')).toBeInTheDocument()
    expect(within(third!).getByText('1 × AB+ platelets')).toBeInTheDocument()
  })

  it('says how old each request is', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(FEED)

    const [first] = await entries('Blood requests')
    expect(within(first!).getByText('40 minutes ago')).toBeInTheDocument()
  })

  it('links a request at the user’s own hospital to its case, and not one from another hospital', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff(FEED)
    await list('Blood requests')

    expect(screen.getByRole('link', { name: 'EC-2026-0002' })).toHaveAttribute('href', '/staff/emergencies/EC-2026-0002')
    expect(screen.queryByRole('link', { name: 'EC-2026-0007' })).toBeNull()
    expect(screen.getByText('EC-2026-0007')).toBeInTheDocument()
  })

  it('shows bed requests when asked, and refetches when the toggle changes', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    renderStaff(FEED)
    await list('Blood requests')

    await userEvent.click(screen.getByRole('radio', { name: 'Beds' }))

    expect(await references('Bed requests')).toEqual(['EC-2026-0002', 'EC-2026-0008', 'EC-2026-0001', 'EC-2026-0009'])
    const urls = fetchMock.mock.calls.map(([input]) => new URL(String(input)).search)
    expect(urls).toContain('?type=blood')
    expect(urls).toContain('?type=bed')
    const [bedFirst] = await entries('Bed requests')
    expect(within(bedFirst!).getByText('1 × ICU bed')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: 'Blood' }))
    expect(await references('Blood requests')).toEqual(['EC-2026-0007', 'EC-2026-0002', 'EC-2026-0008'])
  })

  it('says so when there are no requests of the type', async () => {
    mockStaffApi({ role: 'doctor', feed: [] })
    renderStaff(FEED)

    expect(await screen.findByText('No blood requests in the network right now.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: 'Beds' }))
    expect(await screen.findByText('No bed requests in the network right now.')).toBeInTheDocument()
  })

  it('is open to every role that can see emergencies, and reached from the Emergencies page', async () => {
    for (const role of ['bloodBank', 'pharmacist', 'nurse'] as const) {
      mockStaffApi({ role })
      const { unmount } = renderStaff(FEED)
      expect(await entries('Blood requests')).toHaveLength(3)
      unmount()
      vi.restoreAllMocks()
    }
  })

  it('is linked from the Emergencies page', async () => {
    mockStaffApi({ role: 'pharmacist' })
    renderStaff('/staff/emergencies')

    await userEvent.click(await screen.findByRole('link', { name: 'Network requests' }))

    expect(await screen.findByRole('heading', { name: 'Network requests' })).toBeInTheDocument()
    expect(await entries('Blood requests')).toHaveLength(3)
  })

  it('keeps patients out of the feed', async () => {
    mockStaffApi({ role: 'patient' })
    renderStaff(FEED)

    expect(await screen.findByRole('heading', { name: 'This area is for hospital staff' })).toBeInTheDocument()
  })

  it('shows the network’s requests even when this hospital has none of its own', async () => {
    mockStaffApi({ role: 'doctor', cases: sampleCases(new Date()).slice(1) })
    renderStaff(FEED)

    expect(await references('Blood requests')).toEqual(['EC-2026-0007', 'EC-2026-0008'])
  })
})
