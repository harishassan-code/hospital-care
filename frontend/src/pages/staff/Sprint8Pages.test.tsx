import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi, sampleNotifications } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

const rowheaders = (table: string) =>
  within(screen.getByRole('table', { name: table }))
    .getAllByRole('rowheader')
    .map((cell) => cell.textContent)

describe('AmbulancesPage (story #50)', () => {
  it('lists the fleet with status and lets a nurse register and service an ambulance', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/ambulances')
    await screen.findByRole('table', { name: 'Ambulances' })
    expect(rowheaders('Ambulances')).toEqual(['AMB-CGH-01', 'AMB-CGH-02', 'AMB-CGH-03'])
    expect(screen.getByText('1 of 3 ready to dispatch.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Register ambulance' }))
    await userEvent.type(screen.getByLabelText('Fleet number'), 'amb-cgh-04')
    await userEvent.click(screen.getByRole('button', { name: 'Register ambulance' }))
    expect(await screen.findByRole('rowheader', { name: 'AMB-CGH-04' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Start maintenance AMB-CGH-01' }))
    const row = screen.getByRole('rowheader', { name: 'AMB-CGH-01' }).closest('tr') as HTMLElement
    expect(await within(row).findByText('Maintenance')).toBeInTheDocument()
  })

  it('is read-only for doctors', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/ambulances')
    await screen.findByRole('table', { name: 'Ambulances' })
    expect(screen.queryByRole('button', { name: 'Register ambulance' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Start maintenance/ })).not.toBeInTheDocument()
  })
})

describe('Alerts (story #53)', () => {
  it('counts unread notifications on the bell and keeps a critical banner until acknowledged', async () => {
    mockStaffApi({ role: 'bloodBank', notifications: sampleNotifications(new Date()) })
    renderStaff('/staff/alerts')
    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('Transfer requested for EC-2026-0001')
    expect(await screen.findByRole('link', { name: /need attention|needs attention/ })).toHaveAttribute('href', '/staff/alerts')
    await userEvent.click(within(banner).getByRole('button', { name: 'Acknowledge' }))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })

  it('lists notifications and filters to unread', async () => {
    mockStaffApi({ role: 'nurse', notifications: sampleNotifications(new Date()) })
    renderStaff('/staff/alerts')
    const list = await screen.findByRole('list', { name: 'Notifications' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(2)
    await userEvent.click(within(screen.getByRole('group', { name: 'Show' })).getByRole('button', { name: /Unread/ }))
    expect(within(screen.getByRole('list', { name: 'Notifications' })).getAllByRole('listitem')).toHaveLength(1)
  })
})

describe('CommandCentrePage (story #55)', () => {
  it('shows network totals, shortages and one row per hospital', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/command-centre')
    await screen.findByRole('table', { name: 'Hospitals in the network' })
    expect(rowheaders('Hospitals in the network')).toEqual(['CityCare General Hospital', 'Seaview Hospital'])
    const shortages = screen.getByRole('list', { name: 'Shortages' })
    expect(shortages).toHaveTextContent('CityCare General Hospital: no free ICU bed')
    expect(shortages).toHaveTextContent('O- red cells 1 of 6 minimum')
  })

  it('is admin only', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/command-centre')
    expect((await screen.findAllByText(/can’t|cannot|don’t have/i)).length).toBeGreaterThan(0)
    expect(screen.queryByRole('table', { name: 'Hospitals in the network' })).not.toBeInTheDocument()
  })
})

describe('AuditPage (story #56)', () => {
  it('searches by action prefix and offers a CSV export with the same filters', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/audit')
    await screen.findByRole('table', { name: 'Audit entries' })
    expect(rowheaders('Audit entries')).toEqual(['transfer.requested', 'bed.status_changed'])
    await userEvent.type(screen.getByLabelText(/^Action/), 'transfer.')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(rowheaders('Audit entries')).toEqual(['transfer.requested']))
    expect(screen.getByRole('link', { name: 'Export CSV' }).getAttribute('href')).toContain('/audit/export.csv?action=transfer.')
  })
})

describe('DonorsPage (stories #20 to #22)', () => {
  it('registers a donor, records a deferral and books an appointment', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/donors')
    await screen.findByRole('table', { name: 'Donors' })
    expect(rowheaders('Donors')).toEqual(['DN-0001', 'DN-0002'])

    await userEvent.click(screen.getByRole('button', { name: 'Register donor' }))
    await userEvent.type(screen.getByLabelText('Full name'), 'Donor Three')
    await userEvent.click(screen.getByRole('button', { name: 'Register donor' }))
    expect(await screen.findByText('Registered Donor Three. Donor code DN-0003.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Open Donor One' }))
    await userEvent.type(screen.getByLabelText(/^Deferral reason/), 'Recent travel')
    await userEvent.click(screen.getByRole('button', { name: 'Record deferral' }))
    const row = screen.getByRole('rowheader', { name: 'DN-0001' }).closest('tr') as HTMLElement
    expect(await within(row).findByText(/Deferred/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Open Donor Three' }))
    await userEvent.type(screen.getByLabelText('Appointment'), '2027-03-01T10:00')
    await userEvent.click(screen.getByRole('button', { name: 'Book appointment' }))
    const appointments = await screen.findByRole('list', { name: 'Appointments' })
    expect(appointments).toHaveTextContent('Donor Three (DN-0003)')
    await userEvent.click(within(appointments).getByRole('button', { name: 'Cancel appointment for Donor Three' }))
    expect(await screen.findByText('No upcoming appointments.')).toBeInTheDocument()
  })
})

describe('Overview (story #54)', () => {
  it('shows open emergencies and pending transfers', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff')
    expect(await screen.findByRole('heading', { name: 'Open emergencies' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Pending transfers' })).toBeInTheDocument()
  })
})
