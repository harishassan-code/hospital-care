import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi, sampleAmbulances } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

const tags = () =>
  within(screen.getByRole('table', { name: 'Ambulances' }))
    .getAllByRole('rowheader')
    .map((cell) => cell.textContent)

const rowFor = (tag: string) => screen.getByRole('rowheader', { name: tag }).closest('tr') as HTMLElement

describe('AmbulancesPage (story #50 Ambulance registry)', () => {
  it('lists the hospital’s ambulances with type, base hospital and status', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/ambulances')
    await screen.findByRole('table', { name: 'Ambulances' })
    expect(tags()).toEqual(['AMB-01', 'AMB-02', 'AMB-03', 'AMB-04'])
    const row = rowFor('AMB-02')
    expect(within(row).getByText('Basic life support')).toBeInTheDocument()
    expect(within(row).getByText('CityCare General Hospital')).toBeInTheDocument()
    expect(within(row).getByText('In maintenance')).toBeInTheDocument()
    expect(screen.getByText('2 of 4 available right now.')).toBeInTheDocument()
  })

  it('admins see every hospital’s ambulances', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/ambulances')
    await screen.findByRole('table', { name: 'Ambulances' })
    expect(tags()).toHaveLength(5)
    expect(within(rowFor('AMB-05')).getByText('Seaview Hospital')).toBeInTheDocument()
    expect(screen.getByText('3 of 5 available right now.')).toBeInTheDocument()
  })

  it('filters by type and by status', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/ambulances')
    await screen.findByRole('table', { name: 'Ambulances' })
    const types = within(screen.getByRole('group', { name: 'Show ambulance type' }))
    const statuses = within(screen.getByRole('group', { name: 'Show status' }))
    await userEvent.click(types.getByRole('button', { name: /Advanced life support/ }))
    expect(tags()).toEqual(['AMB-01', 'AMB-04'])
    await userEvent.click(statuses.getByRole('button', { name: /^Available/ }))
    expect(tags()).toEqual(['AMB-01'])
    await userEvent.click(types.getByRole('button', { name: /Patient transport/ }))
    expect(tags()).toEqual(['AMB-03'])
    await userEvent.click(statuses.getByRole('button', { name: /Out of service/ }))
    expect(screen.getByText('No ambulances match. Choose another type or status.')).toBeInTheDocument()
  })

  it('lets a nurse register an ambulance at their own hospital, which then appears in the list', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/ambulances')
    await userEvent.click(await screen.findByRole('button', { name: 'Register ambulance' }))
    expect(screen.queryByLabelText('Base hospital')).not.toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Asset tag/), ' amb-06 ')
    await userEvent.selectOptions(screen.getByLabelText('Type'), 'patientTransport')
    await userEvent.click(screen.getByRole('button', { name: 'Register ambulance' }))
    const row = await screen.findByRole('rowheader', { name: 'AMB-06' })
    expect(within(row.closest('tr') as HTMLElement).getByText('Patient transport')).toBeInTheDocument()
    expect(within(row.closest('tr') as HTMLElement).getByText('CityCare General Hospital')).toBeInTheDocument()
  })

  it('lets an admin pick the base hospital, from active hospitals only', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/ambulances')
    await userEvent.click(await screen.findByRole('button', { name: 'Register ambulance' }))
    const hospital = screen.getByLabelText('Base hospital')
    await within(hospital).findByRole('option', { name: 'Seaview Hospital' })
    expect(within(hospital).queryByRole('option', { name: 'Old Town Blood Centre' })).not.toBeInTheDocument()
    await userEvent.selectOptions(hospital, 'Seaview Hospital')
    await userEvent.type(screen.getByLabelText(/Asset tag/), 'AMB-07')
    await userEvent.click(screen.getByRole('button', { name: 'Register ambulance' }))
    const row = await screen.findByRole('rowheader', { name: 'AMB-07' })
    expect(within(row.closest('tr') as HTMLElement).getByText('Seaview Hospital')).toBeInTheDocument()
  })

  it('checks required fields and shows the server’s duplicate-tag error', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/ambulances')
    await userEvent.click(await screen.findByRole('button', { name: 'Register ambulance' }))
    await userEvent.click(screen.getByRole('button', { name: 'Register ambulance' }))
    expect(screen.getByText('Enter the asset tag, e.g. AMB-04.')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/Asset tag/), 'amb-01')
    await userEvent.click(screen.getByRole('button', { name: 'Register ambulance' }))
    expect(await screen.findByText('This asset tag is already registered at this hospital.')).toBeInTheDocument()
    expect(tags()).toHaveLength(5)
  })

  it('doesn’t offer registration or status buttons to a doctor (view only)', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/ambulances')
    const table = await screen.findByRole('table', { name: 'Ambulances' })
    expect(screen.queryByRole('button', { name: 'Register ambulance' })).not.toBeInTheDocument()
    expect(within(table).queryByRole('columnheader', { name: 'Change status' })).not.toBeInTheDocument()
    expect(within(table).queryAllByRole('button')).toHaveLength(0)
  })

  it('moves an ambulance from its row: saves it through the API, updates the row and announces it', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/ambulances')
    await screen.findByRole('table', { name: 'Ambulances' })
    await userEvent.click(screen.getByRole('button', { name: 'Start maintenance AMB-01' }))
    expect(await screen.findByText('AMB-01 is now in maintenance')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/ambulances/1/actions/'),
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ action: 'startMaintenance' }) }),
    )
    expect(within(rowFor('AMB-01')).getByText('In maintenance')).toBeInTheDocument()
    expect(screen.getByText('1 of 4 available right now.')).toBeInTheDocument()
  })

  it('offers only the moves allowed from the current status', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/ambulances')
    await screen.findByRole('table', { name: 'Ambulances' })
    expect(screen.getByRole('button', { name: 'Finish maintenance AMB-02' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Take out of service AMB-02' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start maintenance AMB-02' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Return to service AMB-04' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Take out of service AMB-04' })).not.toBeInTheDocument()
  })

  it('reloads the list and says the status changed first when the move is refused (409)', async () => {
    const { ambulances } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/ambulances')
    await screen.findByRole('table', { name: 'Ambulances' })
    // Someone else takes AMB-01 out of service before this nurse's move reaches the server.
    ambulances[0] = { ...ambulances[0], status: 'outOfService' }
    await userEvent.click(screen.getByRole('button', { name: 'Start maintenance AMB-01' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'AMB-01: That move is no longer allowed, because the status changed first. The list shows the latest status.',
    )
    expect(within(rowFor('AMB-01')).getByText('Out of service')).toBeInTheDocument()
  })
})

describe('AmbulancesPage: trips (story #51)', () => {
  it('shows the ambulance on a trip with its transfer, offers no status change for it, and filters by On trip', async () => {
    const now = new Date()
    const onTrip = sampleAmbulances(now).map((a) =>
      a.identifier === 'AMB-01' ? { ...a, status: 'dispatched' as const, trip: { id: 4, status: 'enRoute' as const, transferId: 2 } } : a,
    )
    mockStaffApi({ role: 'nurse', ambulances: onTrip })
    renderStaff('/staff/ambulances')
    await screen.findByRole('table', { name: 'Ambulances' })

    const row = rowFor('AMB-01')
    expect(within(row).getByText('On trip')).toBeInTheDocument()
    expect(within(row).getByText('Carrying transfer #2, en route')).toBeInTheDocument()
    expect(within(row).queryByRole('button')).toBeNull()

    const statuses = within(screen.getByRole('group', { name: 'Show status' }))
    await userEvent.click(statuses.getByRole('button', { name: /On trip/ }))
    expect(tags()).toEqual(['AMB-01'])
  })
})
