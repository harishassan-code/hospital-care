import { apiGet, apiPost } from './client'

export type BloodGroup = 'O-' | 'O+' | 'A-' | 'A+' | 'B-' | 'B+' | 'AB-' | 'AB+'
export type Component = 'redCells' | 'plasma' | 'platelets' | 'cryo'
export type UnitStatus = 'quarantined' | 'available' | 'reserved' | 'issued' | 'expired' | 'discarded'
export type ScreeningTest = 'hiv' | 'hbv' | 'hcv' | 'syphilis' | 'malaria'

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

/** Mandatory screening for every unit (story #18). Mirrors ScreeningTest in backend/apps/blood/models.py. */
export const REQUIRED_TESTS: readonly { id: ScreeningTest; label: string }[] = [
  { id: 'hiv', label: 'HIV' },
  { id: 'hbv', label: 'Hepatitis B' },
  { id: 'hcv', label: 'Hepatitis C' },
  { id: 'syphilis', label: 'Syphilis' },
  { id: 'malaria', label: 'Malaria' },
]

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

export interface BloodUnitInput {
  id: string
  group: BloodGroup
  component: Component
  /** ISO timestamp. */
  collectedAt: string
  location: string
}

/** Registers a unit; the server defaults its expiry from the component's shelf life. POST /api/blood/units/ (blood: edit). */
export function createBloodUnit(input: BloodUnitInput): Promise<BloodUnit> {
  return apiPost<BloodUnit>('/blood/units/', input)
}

export interface TestResult {
  test: ScreeningTest
  passed: boolean
  reason: string
  recordedAt: string
}

export interface BloodUnitDetail extends BloodUnit {
  donorId: string | null
  tests: TestResult[]
  /** Required tests not yet recorded as passed. Empty once the unit is released or discarded. */
  missingTests: ScreeningTest[]
}

/** The unit with its screening results. GET /api/blood/units/<id>/ (blood: view). */
export function getBloodUnit(id: string): Promise<BloodUnitDetail> {
  return apiGet<BloodUnitDetail>(`/blood/units/${encodeURIComponent(id)}/`)
}

/**
 * Records one screening result on a quarantined unit (story #18). A failed test discards the unit with
 * `reason`; once every required test has passed the unit is released to available — both automatic.
 * POST /api/blood/units/<id>/tests/ (blood: edit).
 */
export function recordTest(
  id: string,
  input: { test: ScreeningTest; passed: boolean; reason?: string },
): Promise<BloodUnitDetail> {
  return apiPost<BloodUnitDetail>(`/blood/units/${encodeURIComponent(id)}/tests/`, input)
}
