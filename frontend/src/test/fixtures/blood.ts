import { COMPONENTS, type BloodGroup, type BloodUnit, type Component, type UnitStatus } from '../../api/blood'
import { seededRandom } from '../random'

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
