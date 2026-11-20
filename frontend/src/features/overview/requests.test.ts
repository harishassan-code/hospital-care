import { describe, expect, it } from 'vitest'
import type { CaseStatus, EmergencyCase, Severity } from '../../api/emergencies'
import type { Transfer, TransferStatus } from '../../api/transfers'
import { summarizeRequests } from './requests'

const CITYCARE = { id: 1, name: 'CityCare General Hospital' }
const RIVERSIDE = { id: 2, name: 'Riverside Medical Centre' }

const caseOf = (status: CaseStatus, severity: Severity = 'moderate'): EmergencyCase => ({
  id: `EC-${status}-${severity}`,
  severity,
  status,
  patientRef: '',
  hospital: CITYCARE,
  createdBy: 'Dr. Ayesha Khan',
  createdAt: '2026-11-18T09:00:00Z',
  items: [{ type: 'bed', bedType: 'general', quantity: 1 }],
})

/** A transfer from `supplier` to `receiver`: incoming for CityCare when it supplies, outgoing when it receives. */
const transferOf = (id: number, status: TransferStatus, { supplier = CITYCARE, receiver = RIVERSIDE } = {}): Transfer => ({
  id,
  case: { reference: 'EC-2026-0002', severity: 'critical' },
  trip: null,
  etaMinutes: 12,
  itemId: 1,
  resourceType: 'blood',
  need: 'O- red cells',
  supplier,
  receiver,
  quantity: 1,
  approved: 0,
  resources: [],
  status,
  reason: '',
  requestedBy: 'Dr. Ayesha Khan',
  createdAt: '2026-11-18T09:00:00Z',
  history: [],
  actions: [],
})

describe('summarizeRequests: open requests', () => {
  it('counts the four open statuses and leaves out fulfilled, closed and cancelled cases', () => {
    const cases = [
      caseOf('open'),
      caseOf('matching'),
      caseOf('partiallyFulfilled'),
      caseOf('escalated'),
      caseOf('fulfilled'),
      caseOf('closed'),
      caseOf('cancelled'),
    ]
    expect(summarizeRequests(cases, null).cases).toEqual({ open: 4, critical: 0 })
  })

  it('counts open critical cases only, and ignores critical cases that are no longer open', () => {
    const cases = [caseOf('open', 'critical'), caseOf('escalated', 'critical'), caseOf('fulfilled', 'critical'), caseOf('open', 'low')]
    expect(summarizeRequests(cases, null).cases).toEqual({ open: 3, critical: 2 })
  })

  it('is zero for no cases', () => {
    expect(summarizeRequests([], null).cases).toEqual({ open: 0, critical: 0 })
  })

  it('is unavailable when the cases could not be loaded', () => {
    expect(summarizeRequests(null, null).cases).toBeNull()
  })
})

describe('summarizeRequests: transfers', () => {
  it('counts the four pending statuses and leaves out delivered, rejected and cancelled transfers', () => {
    const incoming = [
      transferOf(1, 'requested', { supplier: CITYCARE, receiver: RIVERSIDE }),
      transferOf(2, 'approved', { supplier: CITYCARE, receiver: RIVERSIDE }),
      transferOf(3, 'delivered', { supplier: CITYCARE, receiver: RIVERSIDE }),
      transferOf(4, 'rejected', { supplier: CITYCARE, receiver: RIVERSIDE }),
    ]
    const outgoing = [
      transferOf(5, 'dispatched', { supplier: RIVERSIDE, receiver: CITYCARE }),
      transferOf(6, 'inTransit', { supplier: RIVERSIDE, receiver: CITYCARE }),
      transferOf(7, 'cancelled', { supplier: RIVERSIDE, receiver: CITYCARE }),
    ]
    expect(summarizeRequests(null, { incoming, outgoing }).transfers).toEqual({ pending: 4, toAnswer: 1, outgoing: 2 })
  })

  it('counts "to answer" as incoming transfers still requested, not approved ones', () => {
    const incoming = [transferOf(1, 'requested'), transferOf(2, 'requested'), transferOf(3, 'approved')]
    expect(summarizeRequests(null, { incoming, outgoing: [] }).transfers).toEqual({ pending: 3, toAnswer: 2, outgoing: 0 })
  })

  it('never counts an outgoing request as something to answer', () => {
    const outgoing = [transferOf(1, 'requested', { supplier: RIVERSIDE, receiver: CITYCARE })]
    expect(summarizeRequests(null, { incoming: [], outgoing }).transfers).toEqual({ pending: 1, toAnswer: 0, outgoing: 1 })
  })

  it('counts each transfer once when the same list comes back in both directions (an admin sees the network)', () => {
    const network = [transferOf(1, 'requested'), transferOf(2, 'inTransit'), transferOf(3, 'delivered')]
    expect(summarizeRequests(null, { incoming: network, outgoing: network }).transfers).toEqual({
      pending: 2,
      toAnswer: 1,
      outgoing: 2,
    })
  })

  it('is zero when nothing is pending', () => {
    expect(summarizeRequests(null, { incoming: [], outgoing: [] }).transfers).toEqual({ pending: 0, toAnswer: 0, outgoing: 0 })
  })

  it('is unavailable when the transfers could not be loaded, and the cases still count', () => {
    const summary = summarizeRequests([caseOf('open', 'critical')], null)
    expect(summary.transfers).toBeNull()
    expect(summary.cases).toEqual({ open: 1, critical: 1 })
  })
})
