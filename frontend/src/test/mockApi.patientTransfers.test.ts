import { afterEach, describe, expect, it, vi } from 'vitest'
import { getCase, getPatientTransfers, patientTransferAction, requestPatientTransfer } from '../api/emergencies'
import { sampleCaseTransfer, sampleIncomingPatient } from './fixtures/patientTransfers'
import { mockStaffApi } from './mockApi'

/** The mock stands in for the server, so it must refuse what the server refuses (B17). These pin the rules. */

afterEach(() => vi.restoreAllMocks())

describe('the mock’s patient transfers follow the server (B17)', () => {
  it('asks for a move to a hospital in the case’s list, and lists it as outgoing for the sending hospital', async () => {
    mockStaffApi({ role: 'doctor' })

    const created = await requestPatientTransfer('EC-2026-0002', 2, 'Cath lab')

    expect(created).toMatchObject({
      status: 'requested',
      from: { id: 1 },
      to: { id: 2, name: 'Riverside Medical Centre' },
      note: 'Cath lab',
      actions: ['cancel'],
    })
    expect(await getPatientTransfers('outgoing')).toEqual([expect.objectContaining({ id: created.id })])
  })

  it('refuses a destination that is not in the case’s list, under its field', async () => {
    mockStaffApi({ role: 'doctor' })

    await expect(requestPatientTransfer('EC-2026-0002', 999)).rejects.toMatchObject({
      status: 400,
      body: { destinationId: [expect.any(String)] },
    })
  })

  it('allows one open transfer per case', async () => {
    mockStaffApi({ role: 'doctor' })
    await requestPatientTransfer('EC-2026-0002', 2)

    await expect(requestPatientTransfer('EC-2026-0002', 3)).rejects.toMatchObject({ status: 409 })
  })

  it('confirms arrival at the receiving hospital, and refuses a second confirmation', async () => {
    mockStaffApi({ role: 'doctor', patientTransfers: [sampleIncomingPatient(new Date())] })

    expect(await patientTransferAction(1, 'arrive')).toMatchObject({ status: 'arrived', actions: [] })
    await expect(patientTransferAction(1, 'arrive')).rejects.toMatchObject({ status: 409 })
  })

  it('refuses the sending hospital’s confirmation, and a cancel without a reason', async () => {
    mockStaffApi({ role: 'doctor', patientTransfers: [sampleCaseTransfer(new Date())] })

    await expect(patientTransferAction(2, 'arrive')).rejects.toMatchObject({ status: 403 })
    await expect(patientTransferAction(2, 'cancel', '  ')).rejects.toMatchObject({
      status: 400,
      body: { reason: [expect.any(String)] },
    })
    expect(await patientTransferAction(2, 'cancel', 'Patient stable')).toMatchObject({
      status: 'cancelled',
      reason: 'Patient stable',
    })
  })

  it('carries the transfer flag and the case’s transfers on the case', async () => {
    mockStaffApi({ role: 'doctor', patientTransfers: [sampleCaseTransfer(new Date())] })

    const detail = await getCase('EC-2026-0002')

    expect(detail.transferFlag).toBe(true)
    expect(detail.patientTransfers.map((p) => p.status)).toEqual(['requested'])
  })
})
