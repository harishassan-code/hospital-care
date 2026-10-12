import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

const names = () =>
  within(screen.getByRole('table', { name: 'Hospitals in the network' }))
    .getAllByRole('link')
    .map((a) => a.textContent)

describe('HospitalsPage (story 1.3 Hospital registration)', () => {
  it('lists every hospital, marking deactivated ones', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/hospitals')
    await screen.findByRole('table', { name: 'Hospitals in the network' })
    expect(names()).toEqual(['CityCare General Hospital', 'Seaview Hospital', 'Old Town Blood Centre'])
    const blood = screen.getByRole('link', { name: 'Old Town Blood Centre' }).closest('tr') as HTMLElement
    expect(within(blood).getByText('Deactivated')).toBeInTheDocument()
    expect(within(blood).getByText('Blood bank')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'CityCare General Hospital' })).toHaveAttribute('href', '/staff/hospitals/1')
  })

  it('searches by name or address and filters by type', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/hospitals')
    const search = await screen.findByRole('searchbox', { name: 'Search hospitals' })
    await userEvent.type(search, 'clifton')
    expect(names()).toEqual(['Seaview Hospital'])
    await userEvent.clear(search)
    await userEvent.click(screen.getByRole('button', { name: /Blood bank/ }))
    expect(names()).toEqual(['Old Town Blood Centre'])
    await userEvent.type(search, 'seaview')
    expect(screen.getByText('No hospitals match. Clear the search or choose another type.')).toBeInTheDocument()
  })

  it('offers registration to admins only', async () => {
    mockStaffApi({ role: 'admin' })
    const { unmount } = renderStaff('/staff/hospitals')
    expect(await screen.findByRole('link', { name: 'Register a hospital' })).toHaveAttribute('href', '/staff/hospitals/new')
    unmount()
    vi.restoreAllMocks()
    mockStaffApi({ role: 'pharmacist' })
    renderStaff('/staff/hospitals')
    await screen.findByRole('table', { name: 'Hospitals in the network' })
    expect(screen.queryByRole('link', { name: 'Register a hospital' })).toBeNull()
  })

  it('is closed to patients', async () => {
    mockStaffApi({ role: 'patient' })
    renderStaff('/staff/hospitals')
    expect(await screen.findByRole('heading', { name: 'This area is for hospital staff' })).toBeInTheDocument()
  })
})
