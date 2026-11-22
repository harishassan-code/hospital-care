import type { PatientTransfer } from '../../api/emergencies'

const citycare = { id: 1, name: 'CityCare General Hospital' }
const riverside = { id: 2, name: 'Riverside Medical Centre' }
const northside = { id: 3, name: "Northside Children's Hospital" }

/** The receiving hospital's #42 entry as it stood when the move was asked for: it has everything the case needs. */
const destinationMatch = (hospital: { id: number; name: string }): PatientTransfer['match'] => ({
  rank: 1,
  hospital,
  complete: true,
  recommended: true,
  coverage: '1 of 1',
  coveredCount: 1,
  totalNeeds: 1,
  score: 87.6,
  distanceKm: 4.2,
  travelMinutes: 6,
  covered: [{ itemId: 1, need: 'O- red cells' }],
  unmet: [],
})

/**
 * A critical patient on her way to CityCare General from Northside, asked for a few minutes ago (B17). The receiving
 * hospital sees her on its Emergencies page, before she arrives, and confirms her arrival.
 */
export function sampleIncomingPatient(now: Date): PatientTransfer {
  const minutesAgo = (m: number) => new Date(now.getTime() - m * 60_000).toISOString()
  return {
    id: 1,
    reference: 'EC-2026-0009',
    severity: 'critical',
    status: 'requested',
    from: northside,
    to: citycare,
    needs: ['O- red cells'],
    match: destinationMatch(citycare),
    requestedBy: 'Dr. Omar Siddiqui',
    requestedAt: minutesAgo(5),
    arrivedBy: null,
    arrivedAt: null,
    note: 'Needs the cath lab',
    reason: '',
    actions: ['arrive'],
  }
}

/**
 * The sample case at CityCare General that is short (EC-2026-0002), asked to move to Riverside by the sending hospital
 * (B17). The sending hospital may cancel it.
 */
export function sampleCaseTransfer(now: Date): PatientTransfer {
  return {
    id: 2,
    reference: 'EC-2026-0002',
    severity: 'critical',
    status: 'requested',
    from: citycare,
    to: riverside,
    needs: ['O- red cells', 'ICU bed'],
    match: destinationMatch(riverside),
    requestedBy: 'Dr. Ayesha Khan',
    requestedAt: new Date(now.getTime() - 3 * 60_000).toISOString(),
    arrivedBy: null,
    arrivedAt: null,
    note: '',
    reason: '',
    actions: ['cancel'],
  }
}
