import { seededRandom } from '../lib/random'

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

/** Approximate share of each group among donors in Pakistan (B+ is the most common). */
const GROUP_SHARE: Record<BloodGroup, number> = {
  'B+': 0.33, 'O+': 0.28, 'A+': 0.22, 'AB+': 0.07, 'B-': 0.03, 'O-': 0.025, 'A-': 0.025, 'AB-': 0.02,
}
const COMPONENT_SHARE: Record<Component, number> = { redCells: 0.56, plasma: 0.24, platelets: 0.12, cryo: 0.08 }

function weighted<T extends string>(roll: number, shares: Record<T, number>): T {
  let total = 0
  for (const [key, share] of Object.entries(shares) as [T, number][]) {
    total += share
    if (roll < total) return key
  }
  return Object.keys(shares)[0] as T
}

const DAY = 86_400_000

/** Seeded sample inventory, with dates relative to `now`. */
export function sampleBloodUnits(now: Date, count = 320, seed = 11): BloodUnit[] {
  const rand = seededRandom(seed)
  return Array.from({ length: count }, (_, i) => {
    const group = weighted(rand.next(), GROUP_SHARE)
    const componentId = weighted(rand.next(), COMPONENT_SHARE)
    const component = COMPONENTS.find((c) => c.id === componentId)!
    // A few units run slightly past their shelf life: expired stock waiting to be discarded.
    const ageDays = rand.next() * component.shelfLifeDays * 1.04
    const collected = now.getTime() - ageDays * DAY
    const expires = collected + component.shelfLifeDays * DAY
    const roll = rand.next()
    const status: UnitStatus =
      expires <= now.getTime()
        ? 'expired'
        : ageDays < 1
          ? 'quarantined'
          : roll < 0.08
            ? 'reserved'
            : roll < 0.11
              ? 'issued'
              : 'available'
    return {
      id: `G7731 26 ${String(100_000 + i * 37).padStart(6, '0')}`,
      group,
      component: component.id,
      collectedAt: new Date(collected).toISOString(),
      expiresAt: new Date(expires).toISOString(),
      status,
      location: rand.pick(component.location),
    }
  })
}

/** All units in the blood bank. Returns sample data until the backend provides GET /api/blood/units/. */
export async function getBloodUnits(now = new Date()): Promise<BloodUnit[]> {
  return sampleBloodUnits(now)
}
