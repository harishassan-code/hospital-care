import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Module, Role } from '../../features/staff/roles'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

// Only the booking permission is switchable: no role can see the schedule without it today, so the
// view-only case has to switch it off to exercise the hidden controls.
const mockRoles = { bookingEdit: true }
vi.mock('../../features/staff/roles', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../features/staff/roles')>()
  return {
    ...actual,
    canEdit: (role: Role, module: Module) =>
      module === 'orBookings' ? mockRoles.bookingEdit : actual.canEdit(role, module),
  }
})

afterEach(() => {
  vi.restoreAllMocks()
  mockRoles.bookingEdit = true
})

const PATH = '/staff/operating-rooms/schedule'
const room = (name: string) => screen.findByRole('region', { name })
const lastQuery = (fetchMock: ReturnType<typeof mockStaffApi>['fetchMock']) =>
  new URL(String(fetchMock.mock.calls.at(-1)![0])).search

/** Open the form and fill in the fields that matter here. */
async function fillBooking({ room, start, end, procedure = 'Hernia repair' }: { room: string; start: string; end: string; procedure?: string }) {
  await userEvent.click(screen.getByRole('button', { name: 'Book a slot' }))
  await userEvent.selectOptions(screen.getByLabelText('Room'), room)
  await userEvent.type(screen.getByLabelText('Procedure'), procedure)
  fireEvent.change(screen.getByLabelText('Start time'), { target: { value: start } })
  fireEvent.change(screen.getByLabelText('End time'), { target: { value: end } })
  await userEvent.click(screen.getByRole('button', { name: 'Book slot' }))
}

describe('OperatingRoomSchedulePage (story #29 Operating room scheduling)', () => {
  it('shows each room’s bookings for the day in time order, and an empty state for a free room', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(PATH)
    const or1 = await room('OR 1')
    const times = within(or1)
      .getAllByText(/^\d{2}:\d{2}–\d{2}:\d{2}$/)
      .map((el) => el.textContent)
    expect(times).toEqual(['08:00–10:00', '10:00–12:30'])
    expect(within(or1).getByText('Appendicectomy')).toBeInTheDocument()
    expect(within(or1).getAllByText(/Dr\. Bilal Ahmed/)).toHaveLength(2)
    const cardiac = await room('Cardiac theatre')
    expect(within(cardiac).getByText('CABG')).toBeInTheDocument()
    const trauma = await room('Trauma theatre')
    expect(within(trauma).getByText('No bookings in Trauma theatre on this day.')).toBeInTheDocument()
  })

  it('changing the day asks the server for that day', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff(PATH)
    await room('OR 1')
    fireEvent.change(screen.getByLabelText('Day'), { target: { value: '2030-01-16' } })
    await waitFor(() => expect(lastQuery(fetchMock)).toBe('?date=2030-01-16'))
    expect(await within(await room('OR 1')).findByText('No bookings in OR 1 on this day.')).toBeInTheDocument()
  })

  it('shows the server’s overlap message on the start time and keeps the form open', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff(PATH)
    await room('OR 1')
    await fillBooking({ room: 'OR 1', start: '09:00', end: '09:30' })
    expect(await screen.findByText('OR 1 is already booked from 08:00 to 10:00.')).toBeInTheDocument()
    expect(screen.getByLabelText('Procedure')).toHaveValue('Hernia repair')
  })

  it('checks the end time locally before asking the server', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff(PATH)
    await room('OR 1')
    await fillBooking({ room: 'OR 1', start: '11:00', end: '10:00' })
    expect(screen.getByText('The end time must be after the start time.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('a saved booking appears in its room once the day has refreshed', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff(PATH)
    await room('OR 1')
    await fillBooking({ room: 'Trauma theatre', start: '13:00', end: '14:00' })
    const trauma = await room('Trauma theatre')
    expect(await within(trauma).findByText('13:00–14:00')).toBeInTheDocument()
    expect(within(trauma).getByText('Hernia repair')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Book slot' })).not.toBeInTheDocument()
  })

  it('cancels a booking after confirmation and removes it from the day', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff(PATH)
    const cardiac = await room('Cardiac theatre')
    await userEvent.click(within(cardiac).getByRole('button', { name: 'Cancel CABG in Cardiac theatre at 09:00' }))
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/operating-rooms/bookings/1/cancel/'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(await within(cardiac).findByText('No bookings in Cardiac theatre on this day.')).toBeInTheDocument()
  })

  it('does not cancel when the confirmation is declined', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff(PATH)
    const cardiac = await room('Cardiac theatre')
    await userEvent.click(within(cardiac).getByRole('button', { name: 'Cancel CABG in Cardiac theatre at 09:00' }))
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/cancel/'))).toBe(false)
    expect(within(cardiac).getByText('CABG')).toBeInTheDocument()
  })

  it('a doctor can book but is not offered cancel on a colleague’s booking', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(PATH)
    const cardiac = await room('Cardiac theatre')
    expect(within(cardiac).getByText('CABG')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Book a slot' })).toBeInTheDocument()
    expect(screen.queryAllByRole('button', { name: /^Cancel / })).toHaveLength(0)
  })

  it('shows no book or cancel controls to a role that can only view the schedule', async () => {
    mockRoles.bookingEdit = false
    mockStaffApi({ role: 'nurse' })
    renderStaff(PATH)
    const or1 = await room('OR 1')
    expect(within(or1).getByText('Appendicectomy')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Book a slot' })).not.toBeInTheDocument()
    expect(screen.queryAllByRole('button', { name: /^Cancel / })).toHaveLength(0)
  })
})
