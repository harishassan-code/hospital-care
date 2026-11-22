import type { Ambulance, AmbulanceAction, AmbulanceStatus } from '../../api/ambulances'

type Transition = { action: AmbulanceAction; label: string; next: AmbulanceStatus }

/** The ambulance lifecycle. Same moves as AMBULANCE_LIFECYCLE in backend/apps/ambulances/models.py. */
const TRANSITIONS: Record<AmbulanceStatus, readonly Transition[]> = {
  available: [
    { action: 'startMaintenance', label: 'Start maintenance', next: 'maintenance' },
    { action: 'outOfService', label: 'Take out of service', next: 'outOfService' },
  ],
  maintenance: [
    { action: 'finishMaintenance', label: 'Finish maintenance', next: 'available' },
    { action: 'outOfService', label: 'Take out of service', next: 'outOfService' },
  ],
  outOfService: [{ action: 'returnToService', label: 'Return to service', next: 'maintenance' }],
  // A trip moves a dispatched vehicle back to available (story #51); the registry offers no move from here.
  dispatched: [],
}

export function actionsFor(status: AmbulanceStatus): readonly Transition[] {
  return TRANSITIONS[status]
}

/** The ambulance after `action`. Throws, like the server's 409, when the move isn't allowed. */
export function applyAmbulanceAction(item: Ambulance, action: AmbulanceAction, now: Date): Ambulance {
  const transition = TRANSITIONS[item.status].find((t) => t.action === action)
  if (!transition) throw new Error(`Can't ${action} a vehicle that is ${item.status}`)
  return { ...item, status: transition.next, statusSince: now.toISOString() }
}
