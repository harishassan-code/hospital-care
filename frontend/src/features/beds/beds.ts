import type { Bed, BedAction, BedStatus, Isolation } from '../../api/beds'
import { dateKey } from '../../lib/time'

export type { BedAction }

type Transition = { action: BedAction; label: string; next: BedStatus }

export const STATUS_LABEL: Record<BedStatus, string> = {
  occupied: 'Occupied',
  reserved: 'Reserved',
  cleaning: 'Cleaning',
  free: 'Free',
  outOfService: 'Out of service',
}

export const ISOLATION_LABEL: Record<Isolation, string> = {
  contact: 'Contact precautions',
  droplet: 'Droplet precautions',
  airborne: 'Airborne precautions',
}

/** The bed lifecycle. Only these moves are allowed; everything else is refused. */
const TRANSITIONS: Record<BedStatus, readonly Transition[]> = {
  occupied: [{ action: 'discharge', label: 'Discharge', next: 'cleaning' }],
  cleaning: [{ action: 'markReady', label: 'Mark ready', next: 'free' }],
  free: [
    { action: 'reserve', label: 'Reserve', next: 'reserved' },
    { action: 'outOfService', label: 'Take out of service', next: 'outOfService' },
  ],
  reserved: [{ action: 'cancelReservation', label: 'Cancel reservation', next: 'free' }],
  outOfService: [{ action: 'returnToService', label: 'Return to service', next: 'cleaning' }],
}

export const CLEANING_TARGET_MINUTES = 45

export function actionsFor(status: BedStatus): readonly Transition[] {
  return TRANSITIONS[status]
}

/** The bed after `action`. Leaving "occupied" clears everything about the patient. */
export function applyAction(bed: Bed, action: BedAction, now: Date): Bed {
  const transition = TRANSITIONS[bed.status].find((t) => t.action === action)
  if (!transition) {
    throw new Error(`Can't ${action.replace(/[A-Z]/g, (c) => ` ${c.toLowerCase()}`)} a bed that is ${STATUS_LABEL[bed.status].toLowerCase()}`)
  }
  const next: Bed = { ...bed, status: transition.next, statusSince: now.toISOString() }
  if (bed.status === 'occupied') {
    for (const key of PATIENT_FIELDS) delete next[key]
  }
  return next
}

const PATIENT_FIELDS = ['patient', 'admittedAt', 'expectedDischarge', 'isolation'] as const

export function minutesInStatus(bed: Bed, now: Date): number {
  return Math.round((now.getTime() - new Date(bed.statusSince).getTime()) / 60_000)
}

export function isCleaningOverdue(bed: Bed, now: Date): boolean {
  return bed.status === 'cleaning' && minutesInStatus(bed, now) > CLEANING_TARGET_MINUTES
}

/** Day 1 is the day of admission. */
export function dayOfStay(bed: Bed, now: Date): number {
  if (!bed.admittedAt) return 0
  return Math.floor((now.getTime() - new Date(bed.admittedAt).getTime()) / 86_400_000) + 1
}

export function summarize(beds: Bed[]): Record<BedStatus, number> & { total: number } {
  const counts = { total: beds.length, occupied: 0, reserved: 0, cleaning: 0, free: 0, outOfService: 0 }
  for (const bed of beds) counts[bed.status]++
  return counts
}

export function dischargesToday(beds: Bed[], now: Date): Bed[] {
  const today = dateKey(now)
  return beds.filter((b) => b.status === 'occupied' && b.expectedDischarge === today)
}
