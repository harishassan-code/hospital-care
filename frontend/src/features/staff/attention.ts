import type { Bed, Ward } from '../../api/beds'
import { BLOOD_GROUPS, MINIMUM_STOCK, type BloodUnit, type Component } from '../../api/blood'
import type { Medicine } from '../../api/pharmacy'
import { formatDuration, hoursUntil } from '../../lib/time'
import { CLEANING_TARGET_MINUTES, isCleaningOverdue, minutesInStatus } from '../beds/beds'
import { availableCounts, formatGroup, stockLevel } from '../blood/blood'
import { daysOfSupply, needsReorder, onHand, SUPPLY_CRITICAL_DAYS } from '../pharmacy/pharmacy'
import type { Module } from './roles'

export type Severity = 'critical' | 'warning'

export interface AttentionItem {
  id: string
  severity: Severity
  module: Module
  title: string
  detail: string
  href: string
}

type Sources = { wards: Ward[]; beds: Bed[]; units: BloodUnit[]; medicines: Medicine[] }

const UNIT_NOUN: Record<Component, string> = { redCells: 'red-cell', plasma: 'plasma', platelets: 'platelet', cryo: 'cryo' }
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

function bloodItems(units: BloodUnit[], now: Date): AttentionItem[] {
  const counts = availableCounts(units)
  const low = BLOOD_GROUPS.flatMap((group): AttentionItem[] => {
    const count = counts.redCells[group]
    const minimum = MINIMUM_STOCK.redCells[group]
    const level = stockLevel(count, minimum)
    if (level === 'ok') return []
    return [{
      id: `blood-low-${group}`,
      severity: level === 'critical' ? 'critical' : 'warning',
      module: 'blood',
      title: `${formatGroup(group)} red cells: ${plural(count, 'unit')} left`,
      detail: `Minimum ${minimum}`,
      href: '/staff/blood',
    }]
  })

  const expiring = new Map<Component, number>()
  for (const unit of units) {
    const hours = hoursUntil(unit.expiresAt, now)
    if (unit.status === 'available' && hours > 0 && hours <= 24) {
      expiring.set(unit.component, (expiring.get(unit.component) ?? 0) + 1)
    }
  }
  const soon = [...expiring].map(([component, n]): AttentionItem => ({
    id: `blood-expiring-${component}`,
    severity: 'warning',
    module: 'blood',
    title: `${plural(n, `${UNIT_NOUN[component]} unit`)} ${n === 1 ? 'expires' : 'expire'} within 24 h`,
    detail: 'Use these first or offer them to another hospital',
    href: '/staff/blood',
  }))

  return [...low, ...soon]
}

function bedItems(beds: Bed[], wards: Ward[], now: Date): AttentionItem[] {
  const wardName = new Map(wards.map((w) => [w.id, w.name]))
  return beds
    .filter((bed) => isCleaningOverdue(bed, now))
    .map((bed) => ({
      id: `bed-cleaning-${bed.id}`,
      severity: 'warning',
      module: 'beds',
      title: `${bed.label} cleaning for ${formatDuration(minutesInStatus(bed, now))}`,
      detail: `${wardName.get(bed.ward) ?? bed.ward} · target ${CLEANING_TARGET_MINUTES} min`,
      href: '/staff/beds',
    }))
}

function medicineItems(medicines: Medicine[]): AttentionItem[] {
  return medicines.filter(needsReorder).map((m) => {
    const days = daysOfSupply(m)
    return {
      id: `med-${m.id}`,
      severity: days < SUPPLY_CRITICAL_DAYS ? 'critical' : 'warning',
      module: 'pharmacy',
      title: `${m.name} ${m.strength}: ${days} days of supply left`,
      detail: `${onHand(m)} ${m.unit} on hand · reorder level ${m.reorderLevel}`,
      href: '/staff/pharmacy',
    }
  })
}

/** Everything that needs someone's attention now, critical first. */
export function buildAttention({ wards, beds, units, medicines }: Sources, now: Date): AttentionItem[] {
  const items = [...bloodItems(units, now), ...bedItems(beds, wards, now), ...medicineItems(medicines)]
  return items.sort((a, b) => Number(b.severity === 'critical') - Number(a.severity === 'critical'))
}
