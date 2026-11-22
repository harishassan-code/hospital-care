import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { at } from '../../test/clock'
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

describe('OverviewPage', () => {
  it('summarises every module in a linked tile', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    const tiles = await screen.findByRole('list', { name: 'Status summary' })
    const links = within(tiles).getAllByRole('link')
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/staff/beds', '/#emergency', '/staff/blood', '/staff/pharmacy'])
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
})
