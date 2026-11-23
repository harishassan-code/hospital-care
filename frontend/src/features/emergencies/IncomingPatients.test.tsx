import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { sampleCaseTransfer, sampleIncomingPatient } from '../../test/fixtures/patientTransfers'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

const EMERGENCIES = '/staff/emergencies'
const incoming = async () => screen.findByRole('region', { name: 'Incoming patients' })
const outgoing = async () => screen.findByRole('region', { name: 'Outgoing patients' })

describe('Incoming patients on the Emergencies page (B17, story #65)', () => {
  it('lists a patient on her way here: reference, severity, needs, sending hospital and request time', async () => {
    mockStaffApi({ role: 'doctor', patientTransfers: [sampleIncomingPatient(new Date())] })
    renderStaff(EMERGENCIES)

    const panel = await incoming()
    expect(await within(panel).findByText('EC-2026-0009')).toBeInTheDocument()
    expect(within(panel).getByText('Critical')).toBeInTheDocument()
    expect(within(panel).getByText('O− red cells')).toBeInTheDocument()
    expect(within(panel).getByText("From Northside Children's Hospital", { exact: false })).toBeInTheDocument()
  })

  it('shows no link to the case, which this hospital cannot read until the patient arrives', async () => {
    mockStaffApi({ role: 'doctor', patientTransfers: [sampleIncomingPatient(new Date())] })
    renderStaff(EMERGENCIES)

    const panel = await incoming()
    await within(panel).findByText('EC-2026-0009')
    expect(within(panel).queryByRole('link')).toBeNull()
  })

  it('confirms arrival, then takes the patient off the list and says the case is here now', async () => {
    mockStaffApi({ role: 'nurse', patientTransfers: [sampleIncomingPatient(new Date())] })
    renderStaff(EMERGENCIES)

    const panel = await incoming()
    await userEvent.click(await within(panel).findByRole('button', { name: 'Confirm arrival of EC-2026-0009' }))

    expect(await within(panel).findByText('No patients are on their way here.')).toBeInTheDocument()
    expect(within(panel).getByRole('status')).toHaveTextContent('EC-2026-0009 has arrived. It is on this hospital’s list now.')
  })

  it('says so when no patient is on the way', async () => {
    mockStaffApi({ role: 'doctor', patientTransfers: [] })
    renderStaff(EMERGENCIES)

    expect(await within(await incoming()).findByText('No patients are on their way here.')).toBeInTheDocument()
  })

  it('is not shown to staff who may only read emergencies', async () => {
    mockStaffApi({ role: 'pharmacist', patientTransfers: [sampleIncomingPatient(new Date())] })
    renderStaff(EMERGENCIES)

    await outgoing()
    expect(screen.queryByRole('region', { name: 'Incoming patients' })).toBeNull()
  })
})

describe('Outgoing patients on the Emergencies page (B17)', () => {
  it('lists the patients this hospital is moving, with the status of each move', async () => {
    mockStaffApi({ role: 'doctor', patientTransfers: [sampleCaseTransfer(new Date())] })
    renderStaff(EMERGENCIES)

    const panel = await outgoing()
    expect(await within(panel).findByText('EC-2026-0002')).toBeInTheDocument()
    expect(within(panel).getByText('Requested')).toBeInTheDocument()
    expect(within(panel).getByText('Transfer to Riverside Medical Centre requested')).toBeInTheDocument()
  })

  it('lets an admin confirm arrival for the receiving hospital, which the demo has no login for (functional sweep)', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin', patientTransfers: [sampleCaseTransfer(new Date())] })
    renderStaff(EMERGENCIES)

    const panel = await outgoing()
    await userEvent.click(await within(panel).findByRole('button', { name: 'Confirm arrival of EC-2026-0002 at Riverside Medical Centre' }))
    expect(await within(panel).findByText('EC-2026-0002 has arrived at Riverside Medical Centre. The case is theirs now.')).toBeInTheDocument()
    expect(within(panel).getByText('Arrived')).toBeInTheDocument()
    const paths = fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname)
    expect(paths.some((path) => /^\/api\/patient-transfers\/\d+\/actions\/$/.test(path))).toBe(true)
  })

  it('offers no arrival to the sending hospital’s own staff', async () => {
    mockStaffApi({ role: 'doctor', patientTransfers: [sampleCaseTransfer(new Date())] })
    renderStaff(EMERGENCIES)

    const panel = await outgoing()
    expect(await within(panel).findByText('EC-2026-0002')).toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /Confirm arrival/ })).toBeNull()
  })

  it('says so when this hospital is moving nobody', async () => {
    mockStaffApi({ role: 'doctor', patientTransfers: [] })
    renderStaff(EMERGENCIES)

    expect(await within(await outgoing()).findByText('No patients are being moved from here.')).toBeInTheDocument()
  })
})
