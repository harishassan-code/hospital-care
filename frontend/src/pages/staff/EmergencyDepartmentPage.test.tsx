import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

describe('Emergency department (B22)', () => {
  it('leads with who is next, in triage order, and says what the page is for', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/emergency-department')
    const lead = await screen.findByRole('region', { name: 'The department now' })
    expect(within(lead).getByText('ED-1002B')).toBeInTheDocument() // triage 2 before 4 and 5
    expect(screen.getByText('Who is waiting, who is next, and why is the wait what it is?')).toBeInTheDocument()
    const waiting = screen.getByRole('table', { name: 'Waiting' })
    const tags = within(waiting).getAllByRole('rowheader').map((c) => c.textContent)
    expect(tags).toEqual(['ED-1002B', 'ED-1001A', 'ED-1003C'])
    expect(screen.queryByText(/name/i, { selector: 'th' })).not.toBeInTheDocument()
  })

  it('starts treatment and the patient moves to being treated', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/emergency-department')
    await userEvent.click((await screen.findAllByRole('button', { name: 'Start treatment ED-1002B' }))[0]!)
    await waitFor(() => expect(within(screen.getByRole('table', { name: 'Being treated' })).getByText('ED-1002B')).toBeInTheDocument())
  })

  it('shows its charts once the figures arrive', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/emergency-department')
    expect(await screen.findByRole('img', { name: 'Arrivals per hour today against a typical day' })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Waiting by triage level' })).toBeInTheDocument()
  })

  it('is in the nurse’s menu but not the blood bank’s', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff')
    const nav = await screen.findByRole('navigation', { name: 'Staff' })
    expect(within(nav).queryByRole('link', { name: /Emergency department/ })).not.toBeInTheDocument()
  })
})
