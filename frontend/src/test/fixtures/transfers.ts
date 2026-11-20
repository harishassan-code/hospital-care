import type { Transfer, TransferHistoryEntry } from '../../api/transfers'

const CITYCARE = { id: 1, name: 'CityCare General Hospital' }
const RIVERSIDE = { id: 2, name: 'Riverside Medical Centre' }
const NORTHSIDE = { id: 3, name: "Northside Children's Hospital" }

/**
 * Transfers that CityCare General's staff see (stories #47 to #49), newest first. Incoming (CityCare supplies): #1 asks for
 * platelets and is waiting for an answer; #2 is approved for one ventilator. Outgoing (CityCare asked): #3 is in transit
 * from Riverside, with its three units set aside there, and #4 is waiting for Northside.
 */
export function sampleTransfers(now: Date): Transfer[] {
  const minutesAgo = (m: number) => new Date(now.getTime() - m * 60_000).toISOString()
  const asked = (at: string, by: string): TransferHistoryEntry[] => [{ fromStatus: '', toStatus: 'requested', action: 'request', note: '', actor: by, at }]
  return [
    {
      id: 4,
      case: { reference: 'EC-2026-0002', severity: 'critical' },
      itemId: 1,
      resourceType: 'blood',
      need: 'O- red cells',
      supplier: NORTHSIDE,
      receiver: CITYCARE,
      quantity: 1,
      approved: 0,
      resources: [],
      status: 'requested',
      reason: '',
      requestedBy: 'Dr. Ayesha Khan',
      createdAt: minutesAgo(5),
      history: asked(minutesAgo(5), 'Dr. Ayesha Khan'),
      trip: null,
      etaMinutes: 25,
      actions: [],
    },
    {
      id: 3,
      case: { reference: 'EC-2026-0002', severity: 'critical' },
      itemId: 1,
      resourceType: 'blood',
      need: 'O- red cells',
      supplier: RIVERSIDE,
      receiver: CITYCARE,
      quantity: 3,
      approved: 3,
      resources: ['O- red cells DN-0101', 'O- red cells DN-0102', 'O- red cells DN-0103'],
      status: 'inTransit',
      reason: '',
      requestedBy: 'Dr. Ayesha Khan',
      createdAt: minutesAgo(90),
      history: [
        ...asked(minutesAgo(90), 'Dr. Ayesha Khan'),
        { fromStatus: 'requested', toStatus: 'approved', action: 'approve', note: '', actor: 'Sadia Admin', at: minutesAgo(80) },
        { fromStatus: 'approved', toStatus: 'dispatched', action: 'dispatch', note: '', actor: 'Sadia Admin', at: minutesAgo(60) },
        { fromStatus: 'dispatched', toStatus: 'inTransit', action: 'startTransit', note: 'Van left Riverside', actor: 'Sadia Admin', at: minutesAgo(45) },
      ],
      trip: null,
      etaMinutes: 25,
      actions: [],
    },
    {
      id: 2,
      case: { reference: 'EC-2026-0007', severity: 'critical' },
      itemId: 1,
      resourceType: 'equipment',
      need: 'Ventilator',
      supplier: CITYCARE,
      receiver: RIVERSIDE,
      quantity: 2,
      approved: 1,
      resources: ['Ventilator VENT-002'],
      status: 'approved',
      reason: '',
      requestedBy: 'Dr. Usman Farooq',
      createdAt: minutesAgo(40),
      history: [
        ...asked(minutesAgo(40), 'Dr. Usman Farooq'),
        { fromStatus: 'requested', toStatus: 'approved', action: 'approve', note: 'One free; the other is in use', actor: 'Hina Javed', at: minutesAgo(35) },
      ],
      trip: null,
      etaMinutes: 25,
      actions: [],
    },
    {
      id: 1,
      case: { reference: 'EC-2026-0008', severity: 'high' },
      itemId: 1,
      resourceType: 'blood',
      need: 'AB+ platelets',
      supplier: CITYCARE,
      receiver: RIVERSIDE,
      quantity: 1,
      approved: 0,
      resources: [],
      status: 'requested',
      reason: '',
      requestedBy: 'Dr. Usman Farooq',
      createdAt: minutesAgo(20),
      history: asked(minutesAgo(20), 'Dr. Usman Farooq'),
      trip: null,
      etaMinutes: 25,
      actions: [],
    },
  ]
}
