import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

describe('Staff on duty (B22)', () => {
  it('leads with who is missing and which department is short', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/staffing')
    const lead = await screen.findByRole('region', { name: 'On duty now' })
    expect(lead).toHaveTextContent('1 not in · 1 department short of nurses')
    const notIn = screen.getByRole('table', { name: 'Not in' })
    expect(within(notIn).getByText('Hira Siddiqui')).toBeInTheDocument()
    const ratios = screen.getByRole('list', { name: 'Patients per nurse by department' })
    expect(within(ratios).getAllByRole('listitem')[1]).toHaveTextContent('General medicine20 (at most 8)Short')
  })

  it('lets the nurse in charge mark someone absent', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/staffing')
    await userEvent.click(await screen.findByRole('button', { name: 'Mark absent: Hira Siddiqui' }))
    await waitFor(() => expect(within(screen.getByRole('table', { name: 'Not in' })).getByText('Absent')).toBeInTheDocument())
  })

  it('shows doctors the same, without the actions', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/staffing')
    await screen.findByRole('table', { name: 'Not in' })
    expect(screen.queryByRole('button', { name: /Mark absent/ })).not.toBeInTheDocument()
  })
})
