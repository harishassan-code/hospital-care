import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

const table = () => screen.findByRole('table', { name: 'Operating rooms' })
const names = async () =>
  within(await table())
    .getAllByRole('rowheader')
    .map((cell) => cell.textContent)
const group = (name: string) => screen.getByRole('group', { name })
const lastQuery = (fetchMock: ReturnType<typeof mockStaffApi>['fetchMock']) =>
  new URL(String(fetchMock.mock.calls.at(-1)![0])).search

describe('OperatingRoomsPage (story #28 Operating room registry)', () => {
  it('lists rooms with their capabilities, location and status', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/operating-rooms')
    expect(await names()).toEqual(['Cardiac theatre', 'OR 1', 'Trauma theatre'])
    const row = screen.getByRole('rowheader', { name: 'Cardiac theatre' }).closest('tr') as HTMLElement
    const capabilities = within(row).getByRole('list', { name: 'Capabilities of Cardiac theatre' })
    expect(within(capabilities).getByText('Cardiac')).toBeInTheDocument()
    expect(within(capabilities).getByText('General')).toBeInTheDocument()
    expect(within(row).getByText('Block B, floor 3')).toBeInTheDocument()
    expect(within(row).getByText('In use')).toBeInTheDocument()
  })

  it('filters by capability and status by asking the API for those rooms', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/operating-rooms')
    await table()
    await userEvent.click(within(group('Show capability')).getByRole('button', { name: 'Cardiac' }))
    expect(lastQuery(fetchMock)).toBe('?capability=cardiac')
    expect(await names()).toEqual(['Cardiac theatre'])

    await userEvent.click(within(group('Show status')).getByRole('button', { name: 'In use' }))
    expect(lastQuery(fetchMock)).toBe('?capability=cardiac&status=inUse')

    await userEvent.click(within(group('Show capability')).getByRole('button', { name: 'Trauma' }))
    expect(lastQuery(fetchMock)).toBe('?capability=trauma&status=inUse')
    expect(screen.getByText('No operating rooms match. Choose another capability or status.')).toBeInTheDocument()
  })

  it('lets a nurse register a room with capabilities, which then appears in the list', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/operating-rooms')
    await userEvent.click(await screen.findByRole('button', { name: 'Register operating room' }))
    await userEvent.type(screen.getByLabelText('Name'), 'OR 4')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Pediatric' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'General' }))
    await userEvent.type(screen.getByLabelText(/Location/), 'Children’s block, floor 1')
    await userEvent.click(screen.getByRole('button', { name: 'Register operating room' }))
    const row = (await screen.findByRole('rowheader', { name: 'OR 4' })).closest('tr') as HTMLElement
    const capabilities = within(row).getByRole('list', { name: 'Capabilities of OR 4' })
    expect(within(capabilities).getByText('General')).toBeInTheDocument()
    expect(within(capabilities).getByText('Pediatric')).toBeInTheDocument()
    expect(within(row).getByText('Children’s block, floor 1')).toBeInTheDocument()
  })

  it('checks the required fields and shows the server’s duplicate-name error', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/operating-rooms')
    await userEvent.click(await screen.findByRole('button', { name: 'Register operating room' }))
    await userEvent.click(screen.getByRole('button', { name: 'Register operating room' }))
    expect(screen.getByText('Enter a name for the room, e.g. OR 4.')).toBeInTheDocument()
    expect(screen.getByText('Pick at least one capability.')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Name'), 'or 1')
    await userEvent.click(screen.getByRole('checkbox', { name: 'General' }))
    await userEvent.click(screen.getByRole('button', { name: 'Register operating room' }))
    expect(await screen.findByText('A room with this name is already registered in your hospital.')).toBeInTheDocument()
  })

  it('doesn’t offer registration or status changes to a doctor (view only)', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/operating-rooms')
    const rooms = await table()
    expect(screen.queryByRole('button', { name: 'Register operating room' })).not.toBeInTheDocument()
    expect(within(rooms).queryByRole('columnheader', { name: 'Change status' })).not.toBeInTheDocument()
    expect(within(rooms).queryAllByRole('button')).toHaveLength(0)
  })

  it('changes status from the row, saves it through the API and announces it', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/operating-rooms')
    await table()
    await userEvent.click(screen.getByRole('button', { name: 'Start case OR 1' }))
    expect(await screen.findByText('OR 1 is now in use')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/operating-rooms/2/actions/'),
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ action: 'startCase' }) }),
    )
    const row = screen.getByRole('rowheader', { name: 'OR 1' }).closest('tr') as HTMLElement
    expect(within(row).getByText('In use')).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: 'Finish case OR 1' })).toBeInTheDocument()
  })

  it('links to the day schedule', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/operating-rooms')
    await table()
    expect(screen.getByRole('link', { name: 'Day schedule' })).toHaveAttribute('href', '/staff/operating-rooms/schedule')
  })

  it('offers only the moves allowed from the current status', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/operating-rooms')
    await table()
    expect(screen.getByRole('button', { name: 'Finish cleaning Trauma theatre' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start maintenance Trauma theatre' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start case Trauma theatre' })).not.toBeInTheDocument()
  })

  it('holds a room for a case, then starts the case from the hold (story #43)', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/operating-rooms')
    await table()
    await userEvent.click(screen.getByRole('button', { name: 'Reserve OR 1' }))
    expect(await screen.findByText('OR 1 is now reserved')).toBeInTheDocument()
    const row = screen.getByRole('rowheader', { name: 'OR 1' }).closest('tr') as HTMLElement
    expect(within(row).getByText('Reserved')).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: 'Start case OR 1' })).toBeInTheDocument()
    expect(within(row).getByRole('button', { name: 'Cancel reservation OR 1' })).toBeInTheDocument()
  })
})
