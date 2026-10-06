import { apiGet } from './client'

export type BloodGroup = 'O-' | 'O+' | 'A-' | 'A+' | 'B-' | 'B+' | 'AB-' | 'AB+'
export type Component = 'redCells' | 'plasma' | 'platelets' | 'cryo'
export type UnitStatus = 'quarantined' | 'available' | 'reserved' | 'issued' | 'expired'

export interface BloodUnit {
  /** Donation identification number in ISBT 128 layout: facility, year, sequence. */
  id: string
  group: BloodGroup
  component: Component
  collectedAt: string
  expiresAt: string
  status: UnitStatus
  location: string
}

export const BLOOD_GROUPS: readonly BloodGroup[] = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']

/** Shelf life and storage per component. Configurable per hospital; these are common defaults. */
export const COMPONENTS: readonly {
  id: Component
  label: string
  shelfLifeDays: number
  storage: string
  location: readonly string[]
}[] = [
  { id: 'redCells', label: 'Red cells', shelfLifeDays: 42, storage: '2–6 °C', location: ['Blood fridge 1', 'Blood fridge 2'] },
  { id: 'plasma', label: 'Plasma', shelfLifeDays: 365, storage: '≤ −25 °C', location: ['Plasma freezer A'] },
  { id: 'platelets', label: 'Platelets', shelfLifeDays: 5, storage: '20–24 °C, agitated', location: ['Platelet agitator'] },
  { id: 'cryo', label: 'Cryo', shelfLifeDays: 365, storage: '≤ −25 °C', location: ['Plasma freezer B'] },
]

/** Minimum stock (par level) per component and group, sized to demand. */
export const MINIMUM_STOCK: Record<Component, Record<BloodGroup, number>> = {
  redCells: { 'O-': 6, 'O+': 30, 'A-': 4, 'A+': 20, 'B-': 4, 'B+': 30, 'AB-': 2, 'AB+': 8 },
  plasma: { 'O-': 2, 'O+': 10, 'A-': 2, 'A+': 8, 'B-': 2, 'B+': 10, 'AB-': 2, 'AB+': 6 },
  platelets: { 'O-': 1, 'O+': 3, 'A-': 1, 'A+': 3, 'B-': 1, 'B+': 3, 'AB-': 0, 'AB+': 1 },
  cryo: { 'O-': 0, 'O+': 2, 'A-': 0, 'A+': 2, 'B-': 0, 'B+': 2, 'AB-': 0, 'AB+': 1 },
}

/** Every unit in the blood bank; past-expiry units come back as "expired". GET /api/blood/units/ (blood: view). */
export function getBloodUnits(): Promise<BloodUnit[]> {
  return apiGet<BloodUnit[]>('/blood/units/')
}
