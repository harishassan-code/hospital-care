import type { Equipment, EquipmentAction, EquipmentStatus } from '../../api/equipment'

type Transition = { action: EquipmentAction; label: string; next: EquipmentStatus }

/** The equipment lifecycle. Same moves as EQUIPMENT_LIFECYCLE in backend/apps/equipment/models.py. */
const TRANSITIONS: Record<EquipmentStatus, readonly Transition[]> = {
  available: [
    { action: 'use', label: 'Mark in use', next: 'inUse' },
    { action: 'reserve', label: 'Reserve', next: 'reserved' },
    { action: 'startMaintenance', label: 'Start maintenance', next: 'maintenance' },
    { action: 'outOfService', label: 'Take out of service', next: 'outOfService' },
  ],
  reserved: [
    { action: 'use', label: 'Mark in use', next: 'inUse' },
    { action: 'cancelReservation', label: 'Cancel reservation', next: 'available' },
  ],
  inUse: [
    { action: 'release', label: 'Release', next: 'available' },
    { action: 'startMaintenance', label: 'Start maintenance', next: 'maintenance' },
  ],
  maintenance: [
    { action: 'finishMaintenance', label: 'Finish maintenance', next: 'available' },
    { action: 'outOfService', label: 'Take out of service', next: 'outOfService' },
  ],
  outOfService: [{ action: 'returnToService', label: 'Return to service', next: 'maintenance' }],
}

export function actionsFor(status: EquipmentStatus): readonly Transition[] {
  return TRANSITIONS[status]
}

/** The item after `action`. Throws, like the server's 409, when the move isn't allowed. */
export function applyEquipmentAction(item: Equipment, action: EquipmentAction, now: Date): Equipment {
  const transition = TRANSITIONS[item.status].find((t) => t.action === action)
  if (!transition) throw new Error(`Can't ${action} a piece of equipment that is ${item.status}`)
  return { ...item, status: transition.next, statusSince: now.toISOString() }
}
