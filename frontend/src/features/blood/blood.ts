import { BLOOD_GROUPS, COMPONENTS, type BloodGroup, type BloodUnit, type Component, type UnitStatus } from '../../api/blood'

export type StockLevel = 'ok' | 'low' | 'critical'

export const UNIT_STATUS_LABEL: Record<UnitStatus, string> = {
  quarantined: 'Quarantined (testing)',
  available: 'Available',
  reserved: 'Reserved',
  issued: 'Issued',
  expired: 'Expired',
}

export const COMPONENT_LABEL = Object.fromEntries(COMPONENTS.map((c) => [c.id, c.label])) as Record<Component, string>

/** "O−" with a true minus sign, for display. Data keeps the ASCII "O-". */
export function formatGroup(group: BloodGroup): string {
  return group.replace('-', '−')
}

const abo = (group: BloodGroup) => group.slice(0, -1)
const antigens = (group: BloodGroup) => new Set(abo(group).replace('O', '').split('').filter(Boolean))
const isRhNegative = (group: BloodGroup) => group.endsWith('-')

/**
 * Donor groups compatible with a recipient, in standard group order.
 * Red cells: the donor must carry no ABO antigen the recipient lacks, and Rh− recipients get Rh− units.
 * Plasma: the reverse — the donor's ABO antigens must cover the recipient's (AB plasma suits everyone);
 * Rh doesn't apply. This is a coordination aid; the lab confirms with a crossmatch.
 */
export function compatibleDonors(recipient: BloodGroup, component: 'redCells' | 'plasma'): BloodGroup[] {
  const has = antigens(recipient)
  return BLOOD_GROUPS.filter((donor) => {
    const donorAntigens = antigens(donor)
    if (component === 'plasma') return [...has].every((a) => donorAntigens.has(a))
    const aboOk = [...donorAntigens].every((a) => has.has(a))
    return aboOk && (!isRhNegative(recipient) || isRhNegative(donor))
  })
}

/** Low below the minimum, critical below half of it. */
export function stockLevel(count: number, minimum: number): StockLevel {
  if (count < minimum / 2) return 'critical'
  if (count < minimum) return 'low'
  return 'ok'
}

export function availableCounts(units: BloodUnit[]): Record<Component, Record<BloodGroup, number>> {
  const counts = Object.fromEntries(
    COMPONENTS.map((c) => [c.id, Object.fromEntries(BLOOD_GROUPS.map((g) => [g, 0]))]),
  ) as Record<Component, Record<BloodGroup, number>>
  for (const unit of units) {
    if (unit.status === 'available') counts[unit.component][unit.group]++
  }
  return counts
}

/** First-expiry-first-out: the unit that expires soonest is used first. */
export function sortFefo(units: BloodUnit[]): BloodUnit[] {
  return [...units].sort((a, b) => a.expiresAt.localeCompare(b.expiresAt))
}
