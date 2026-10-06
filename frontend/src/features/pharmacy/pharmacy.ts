import type { Batch, Medicine } from '../../api/pharmacy'
import { fromDateKey } from '../../lib/time'

export type PharmacyFilter = 'all' | 'reorder' | 'expiring' | 'highAlert' | 'controlled'

/** A batch inside this window counts as expiring soon. */
export const EXPIRING_WITHIN_DAYS = 90
/** Less stock than this many days of use is critical. */
export const SUPPLY_CRITICAL_DAYS = 2

export function onHand(medicine: Medicine): number {
  return medicine.batches.reduce((sum, batch) => sum + batch.quantity, 0)
}

/** How long current stock lasts at the average daily use, to one decimal. */
export function daysOfSupply(medicine: Medicine): number {
  if (medicine.dailyUse <= 0) return Infinity
  return Math.round((onHand(medicine) / medicine.dailyUse) * 10) / 10
}

/** Stock has fallen to the reorder level: order now so it arrives before running out. */
export function needsReorder(medicine: Medicine): boolean {
  return onHand(medicine) <= medicine.reorderLevel
}

export function nearestExpiry(medicine: Medicine): Batch | undefined {
  return medicine.batches
    .filter((batch) => batch.quantity > 0)
    .reduce<Batch | undefined>((soonest, batch) => (!soonest || batch.expiresOn < soonest.expiresOn ? batch : soonest), undefined)
}

/** Whole days from today until a "YYYY-MM-DD" date; negative once it has passed. */
export function daysUntil(dateKey: string, now: Date): number {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((fromDateKey(dateKey).getTime() - today.getTime()) / 86_400_000)
}

export function expiresSoon(medicine: Medicine, now: Date): boolean {
  const batch = nearestExpiry(medicine)
  return batch !== undefined && daysUntil(batch.expiresOn, now) <= EXPIRING_WITHIN_DAYS
}

const MATCHES: Record<PharmacyFilter, (m: Medicine, now: Date) => boolean> = {
  all: () => true,
  reorder: needsReorder,
  expiring: expiresSoon,
  highAlert: (m) => m.highAlert,
  controlled: (m) => m.controlled,
}

export function filterMedicines(medicines: Medicine[], filter: PharmacyFilter, query: string, now: Date): Medicine[] {
  const q = query.trim().toLowerCase()
  return medicines.filter(
    (m) => MATCHES[filter](m, now) && (!q || `${m.name} ${m.category}`.toLowerCase().includes(q)),
  )
}
