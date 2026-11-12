import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

const tags = () =>
  within(screen.getByRole('table', { name: 'Equipment' }))
    .getAllByRole('rowheader')
    .map((cell) => cell.textContent)

describe('EquipmentPage (story #26 Equipment registry)', () => {
  it('lists equipment with type, location and status', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/equipment')
    await screen.findByRole('table', { name: 'Equipment' })
    expect(tags()).toEqual(['VENT-001', 'VENT-002', 'VENT-003', 'DEFIB-001', 'DIAL-001'])
    const row = screen.getByRole('rowheader', { name: 'VENT-003' }).closest('tr') as HTMLElement
    expect(within(row).getByText('HDU')).toBeInTheDocument()
    expect(within(row).getByText('Maintenance')).toBeInTheDocument()
    expect(screen.getByText('2 of 5 available right now.')).toBeInTheDocument()
  })

  it('filters by type and by status', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/equipment')
    await screen.findByRole('table', { name: 'Equipment' })
    await userEvent.click(within(screen.getByRole('group', { name: 'Show equipment type' })).getByRole('button', { name: /Ventilators/ }))
    expect(tags()).toEqual(['VENT-001', 'VENT-002', 'VENT-003'])
    await userEvent.click(within(screen.getByRole('group', { name: 'Show status' })).getByRole('button', { name: /^Available/ }))
    expect(tags()).toEqual(['VENT-002'])
    await userEvent.click(within(screen.getByRole('group', { name: 'Show status' })).getByRole('button', { name: /Out of service/ }))
    expect(screen.getByText('No equipment matches. Choose another type or status.')).toBeInTheDocument()
  })

  it('lets a nurse register equipment, which then appears in the list', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/equipment')
    await userEvent.click(await screen.findByRole('button', { name: 'Register equipment' }))
    await userEvent.type(screen.getByLabelText(/Asset tag/), 'mon-007')
    await userEvent.selectOptions(screen.getByLabelText('Type'), 'monitor')
    await userEvent.type(screen.getByLabelText(/Location/), 'Medical A')
    await userEvent.click(screen.getByRole('button', { name: 'Register equipment' }))
    const row = (await screen.findByRole('rowheader', { name: 'MON-007' })).closest('tr') as HTMLElement
    expect(within(row).getByText('Patient monitor')).toBeInTheDocument()
    expect(within(row).getByText('Medical A')).toBeInTheDocument()
  })

  it('checks required fields and shows the server’s duplicate-tag error', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/equipment')
    await userEvent.click(await screen.findByRole('button', { name: 'Register equipment' }))
    await userEvent.click(screen.getByRole('button', { name: 'Register equipment' }))
    expect(screen.getByText('Enter the asset tag, e.g. VENT-006.')).toBeInTheDocument()
    expect(screen.getByText('Say where the equipment is kept.')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Asset tag/), 'vent-001')
    await userEvent.type(screen.getByLabelText(/Location/), 'ICU')
    await userEvent.click(screen.getByRole('button', { name: 'Register equipment' }))
    expect(await screen.findByText('This asset tag is already registered in your hospital.')).toBeInTheDocument()
  })

  it('doesn’t offer registration to doctors (view only)', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/equipment')
    await screen.findByRole('table', { name: 'Equipment' })
    expect(screen.queryByRole('button', { name: 'Register equipment' })).not.toBeInTheDocument()
  })
})
