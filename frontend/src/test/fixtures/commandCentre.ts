import type { BedType } from '../../api/beds'
import { BLOOD_GROUPS, MINIMUM_STOCK, type BloodGroup, type Component } from '../../api/blood'
import type { CommandCentre, HospitalFigures, NetworkTotals } from '../../api/commandCentre'
import type { EquipmentType } from '../../api/equipment'
import type { ResourceType } from '../../api/emergencies'
import { stockLevel } from '../../features/blood/blood'

/** What one hospital has, in the shape the command centre API returns. Levels are worked out from the minimums. */
type Spec = {
  red: Record<BloodGroup, number>
  /** [usable, of which near expiry] per component. */
  components: Record<Component, [number, number]>
  beds: Record<BedType, number>
  equipment: Record<EquipmentType, number>
  operatingRooms: number
  cases: { active: number; escalated: number }
  open: Record<ResourceType, number>
}

function hospital(id: number, name: string, spec: Spec): HospitalFigures {
  return {
    id,
    name,
    redCells: BLOOD_GROUPS.map((group) => ({
      group,
      available: spec.red[group],
      minimum: MINIMUM_STOCK.redCells[group],
      level: stockLevel(spec.red[group], MINIMUM_STOCK.redCells[group]),
    })),
    components: Object.fromEntries(
      Object.entries(spec.components).map(([component, [usable, nearExpiry]]) => [component, { usable, nearExpiry }]),
    ) as HospitalFigures['components'],
    beds: spec.beds,
    equipment: spec.equipment,
    operatingRooms: spec.operatingRooms,
    cases: spec.cases,
    open: spec.open,
  }
}

/** The network totals: sums of the hospital rows, counts only (story #55). */
export function networkTotals(hospitals: HospitalFigures[]): NetworkTotals {
  const sum = (pick: (h: HospitalFigures) => number) => hospitals.reduce((total, h) => total + pick(h), 0)
  const sumBy = <K extends string>(keys: readonly K[], pick: (h: HospitalFigures, key: K) => number) =>
    Object.fromEntries(keys.map((key) => [key, sum((h) => pick(h, key))])) as Record<K, number>
  const componentKeys = ['redCells', 'plasma', 'platelets', 'cryo'] as const
  return {
    redCells: BLOOD_GROUPS.map((group, i) => ({
      group,
      available: sum((h) => h.redCells[i]!.available),
    })),
    components: Object.fromEntries(
      componentKeys.map((c) => [
        c,
        { usable: sum((h) => h.components[c].usable), nearExpiry: sum((h) => h.components[c].nearExpiry) },
      ]),
    ) as NetworkTotals['components'],
    beds: sumBy(['icu', 'emergency', 'general', 'isolation', 'nicu'] as const, (h, key) => h.beds[key]),
    equipment: sumBy(['ventilator', 'monitor', 'defibrillator', 'dialysis'] as const, (h, key) => h.equipment[key]),
    operatingRooms: sum((h) => h.operatingRooms),
    cases: { active: sum((h) => h.cases.active), escalated: sum((h) => h.cases.escalated) },
    open: sumBy(['blood', 'bed', 'equipment', 'operatingRoom'] as const, (h, key) => h.open[key]),
  }
}

/**
 * The network as the command centre API answers it: hospitals with a critical shortage first, then the rest by name.
 * CityCare General is short of several groups (O− and A− critical); the other two have every group at or above its minimum.
 */
export function sampleCommandCentre(now: Date): CommandCentre {
  const hospitals = [
    hospital(1, 'CityCare General Hospital', {
      red: { 'O-': 0, 'O+': 22, 'A-': 1, 'A+': 20, 'B-': 4, 'B+': 12, 'AB-': 1, 'AB+': 8 },
      components: { redCells: [64, 6], plasma: [18, 2], platelets: [3, 2], cryo: [4, 0] },
      beds: { icu: 3, emergency: 2, general: 9, isolation: 1, nicu: 0 },
      equipment: { ventilator: 2, monitor: 4, defibrillator: 1, dialysis: 0 },
      operatingRooms: 2,
      cases: { active: 4, escalated: 2 },
      open: { blood: 7, bed: 3, equipment: 2, operatingRoom: 1 },
    }),
    hospital(2, 'Old Town Blood Centre', {
      red: { 'O-': 9, 'O+': 40, 'A-': 5, 'A+': 25, 'B-': 6, 'B+': 35, 'AB-': 3, 'AB+': 10 },
      components: { redCells: [130, 0], plasma: [30, 0], platelets: [0, 0], cryo: [2, 0] },
      beds: { icu: 0, emergency: 0, general: 0, isolation: 0, nicu: 0 },
      equipment: { ventilator: 0, monitor: 0, defibrillator: 0, dialysis: 0 },
      operatingRooms: 0,
      cases: { active: 0, escalated: 0 },
      open: { blood: 0, bed: 0, equipment: 0, operatingRoom: 0 },
    }),
    hospital(3, 'Seaview Hospital', {
      red: { 'O-': 8, 'O+': 40, 'A-': 6, 'A+': 25, 'B-': 5, 'B+': 35, 'AB-': 3, 'AB+': 10 },
      components: { redCells: [121, 4], plasma: [28, 0], platelets: [4, 0], cryo: [2, 0] },
      beds: { icu: 1, emergency: 4, general: 12, isolation: 0, nicu: 0 },
      equipment: { ventilator: 1, monitor: 2, defibrillator: 2, dialysis: 1 },
      operatingRooms: 3,
      cases: { active: 1, escalated: 0 },
      open: { blood: 0, bed: 0, equipment: 0, operatingRoom: 1 },
    }),
  ]
  return {
    updatedAt: now.toISOString(),
    nearExpiryDays: 3,
    totals: networkTotals(hospitals),
    hospitals,
  }
}
