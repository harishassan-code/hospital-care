import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SAMPLE_NOON } from '../../test/fixtures/specialists'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(SAMPLE_NOON))
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const windowsTable = () => screen.getByRole('table', { name: 'Upcoming on-call times' })
const rowText = () => within(windowsTable()).getAllByRole('row').slice(1).map((row) => row.textContent)

/** Fill the add-window form: Karachi days and clock times. */
function fillWindow(start: { date: string; time: string }, end: { date: string; time: string }) {
  fireEvent.change(screen.getByLabelText('Start date'), { target: { value: start.date } })
  fireEvent.change(screen.getByLabelText('Start time'), { target: { value: start.time } })
  fireEvent.change(screen.getByLabelText('End date'), { target: { value: end.date } })
  fireEvent.change(screen.getByLabelText('End time'), { target: { value: end.time } })
}

describe('SpecialistDetailPage (stories #61, #62)', () => {
  it('shows the profile, its hospital, and the on-call times ahead in Karachi time', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/specialists/1')
    expect(await screen.findByRole('heading', { name: 'Dr. Ayesha Khan' })).toBeInTheDocument()
    expect(screen.getByText('Cardiology')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Dr. Ayesha Khan' })).getByText('CityCare General Hospital')).toBeInTheDocument()
    expect(screen.getByText('On call until 20:00')).toBeInTheDocument()
    expect(rowText()).toEqual([expect.stringContaining('Wed 18 Nov 08:00')])
    expect(rowText()[0]).toContain('Wed 18 Nov 20:00')
  })

  it('shows a deactivated specialist as deactivated and never on call', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/specialists/4')
    expect(await screen.findByText('Deactivated')).toBeInTheDocument()
    expect(screen.getByText('Not on call')).toBeInTheDocument()
  })

  it('shows a doctor the times, but no edit link, remove button or add form', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/specialists/1')
    await screen.findByRole('heading', { name: 'Dr. Ayesha Khan' })
    expect(screen.queryByRole('link', { name: 'Edit details' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Remove/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Add an on-call time' })).not.toBeInTheDocument()
  })

  it('lets a nurse add an overnight on-call time, which then shows in the list', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/2')
    await screen.findByRole('heading', { name: 'Dr. Usman Farooq' })
    fillWindow({ date: '2026-11-19', time: '20:00' }, { date: '2026-11-20', time: '08:00' })
    await userEvent.click(screen.getByRole('button', { name: 'Add on-call time' }))
    expect(await screen.findByText('Added on-call from Thu 19 Nov 20:00 to Fri 20 Nov 08:00.')).toBeInTheDocument()
    expect(rowText().some((text) => text?.includes('Thu 19 Nov 20:00') && text.includes('Fri 20 Nov 08:00'))).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/specialists/2/on-call/'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ startsAt: '2026-11-19T20:00:00+05:00', endsAt: '2026-11-20T08:00:00+05:00' }),
      }),
    )
  })

  it('shows an overlap on the start time field, in the server’s words', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/1')
    await screen.findByRole('heading', { name: 'Dr. Ayesha Khan' })
    fillWindow({ date: '2026-11-18', time: '18:00' }, { date: '2026-11-18', time: '22:00' })
    await userEvent.click(screen.getByRole('button', { name: 'Add on-call time' }))
    const message = 'Overlaps an on-call window from 18 Nov 08:00 to 18 Nov 20:00.'
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.getByLabelText('Start time')).toHaveAttribute('aria-describedby', expect.stringContaining('-error'))
    expect(screen.getByRole('alert')).toHaveTextContent('The on-call time wasn’t saved. Fix the fields marked above.')
  })

  it('refuses an end that isn’t after the start, before it sends anything', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/2')
    await screen.findByRole('heading', { name: 'Dr. Usman Farooq' })
    fillWindow({ date: '2026-11-19', time: '20:00' }, { date: '2026-11-19', time: '08:00' })
    await userEvent.click(screen.getByRole('button', { name: 'Add on-call time' }))
    expect(await screen.findByText('The on-call time must end after it starts.')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('asks for every part of a new window', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/2')
    await screen.findByRole('heading', { name: 'Dr. Usman Farooq' })
    await userEvent.click(screen.getByRole('button', { name: 'Add on-call time' }))
    expect(screen.getByText('Pick the day it starts.')).toBeInTheDocument()
    expect(screen.getByText('Pick the end time.')).toBeInTheDocument()
  })

  it('removes a window that has not started, and drops it from the list', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/2')
    await screen.findByRole('heading', { name: 'Dr. Usman Farooq' })
    await userEvent.click(screen.getByRole('button', { name: 'Remove the on-call time from Wed 18 Nov 20:00' }))
    expect(await screen.findByText('Removed the on-call time from Wed 18 Nov 20:00.')).toBeInTheDocument()
    expect(screen.getByText('No on-call times ahead.')).toBeInTheDocument()
  })

  it('offers no remove button for a window that has started', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/1')
    await screen.findByRole('heading', { name: 'Dr. Ayesha Khan' })
    expect(screen.queryByRole('button', { name: /^Remove the on-call time/ })).not.toBeInTheDocument()
  })

  it('says so when the server refuses to remove a window that has started since the page loaded', async () => {
    mockStaffApi({ role: 'nurse' })
    vi.setSystemTime(new Date('2026-11-18T07:00:00+05:00'))
    renderStaff('/staff/specialists/1')
    await screen.findByRole('heading', { name: 'Dr. Ayesha Khan' })
    vi.setSystemTime(new Date('2026-11-18T09:00:00+05:00'))
    await userEvent.click(screen.getByRole('button', { name: 'Remove the on-call time from Wed 18 Nov 08:00' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('This window has started, so it stays as history.')
    expect(rowText()).toHaveLength(1)
  })

  it('says when the specialist doesn’t exist', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/specialists/999')
    expect(await screen.findByText('No specialist with that id.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '← All specialists' })).toHaveAttribute('href', '/staff/specialists')
  })

  it('lets an admin reach the edit form from the profile', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/specialists/1')
    expect(await screen.findByRole('link', { name: 'Edit details' })).toHaveAttribute('href', '/staff/specialists/1/edit')
  })
})
