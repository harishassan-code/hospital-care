import type { Bed, BedBoard, Patient, Ward } from '../../api/beds'
import { seededRandom, type Random } from '../random'
import { dateKey } from '../../lib/time'

type WardPlan = Ward & { prefix: string; size: number; occupancy: number; ages: [number, number] }

const PLAN: WardPlan[] = [
  { id: 'icu', name: 'ICU', kind: 'Intensive care', prefix: 'ICU', size: 10, occupancy: 0.9, ages: [18, 85] },
  { id: 'hdu', name: 'HDU', kind: 'High dependency', prefix: 'HDU', size: 8, occupancy: 0.85, ages: [18, 85] },
  { id: 'medA', name: 'Medical A', kind: 'General medicine', prefix: 'MA', size: 24, occupancy: 0.8, ages: [18, 92] },
  { id: 'surgB', name: 'Surgical B', kind: 'General surgery', prefix: 'SB', size: 24, occupancy: 0.75, ages: [16, 88] },
  { id: 'paeds', name: 'Paediatrics', kind: 'Children', prefix: 'PD', size: 16, occupancy: 0.62, ages: [1, 14] },
  { id: 'maternity', name: 'Maternity', kind: 'Obstetrics', prefix: 'MT', size: 18, occupancy: 0.7, ages: [18, 42] },
  { id: 'isolation', name: 'Isolation', kind: 'Infection control', prefix: 'ISO', size: 6, occupancy: 0.67, ages: [18, 80] },
]

const LETTERS = 'ABDFGHIKMNORSTUYZ'
const minutesAgo = (now: Date, minutes: number) => new Date(now.getTime() - minutes * 60_000).toISOString()

function patient(rand: Random, plan: WardPlan): Patient {
  const initials = `${rand.pick([...LETTERS])}.${rand.pick([...LETTERS])}.`
  const sex = plan.id === 'maternity' ? 'F' : rand.pick(['F', 'M'] as const)
  return { initials, age: rand.int(...plan.ages), sex }
}

function occupiedBed(rand: Random, plan: WardPlan, base: Bed, now: Date): Bed {
  const stayMinutes = rand.int(120, 60 * 24 * 12)
  const daysToDischarge = rand.pick([0, 0, 1, 1, 2, 3, 5])
  const discharge = new Date(now)
  discharge.setDate(discharge.getDate() + daysToDischarge)
  const isolation =
    plan.id === 'isolation'
      ? rand.pick(['airborne', 'droplet', 'contact'] as const)
      : rand.chance(0.08)
        ? 'contact'
        : undefined
  return {
    ...base,
    status: 'occupied',
    statusSince: minutesAgo(now, stayMinutes),
    admittedAt: minutesAgo(now, stayMinutes),
    patient: patient(rand, plan),
    expectedDischarge: dateKey(discharge),
    isolation,
  }
}

/** Seeded sample bed board, with times relative to `now`. */
export function sampleBedBoard(now: Date, seed = 7): BedBoard {
  const rand = seededRandom(seed)
  const beds: Bed[] = []
  for (const plan of PLAN) {
    for (let n = 1; n <= plan.size; n++) {
      const label = `${plan.prefix}-${String(n).padStart(2, '0')}`
      const base: Bed = { id: label, ward: plan.id, label, status: 'free', statusSince: minutesAgo(now, rand.int(10, 600)) }
      if (rand.chance(plan.occupancy)) {
        beds.push(occupiedBed(rand, plan, base, now))
        continue
      }
      const roll = rand.next()
      if (roll < 0.3) beds.push({ ...base, status: 'cleaning', statusSince: minutesAgo(now, rand.int(5, 75)) })
      else if (roll < 0.5) beds.push({ ...base, status: 'reserved' })
      else if (roll < 0.95) beds.push(base)
      else beds.push({ ...base, status: 'outOfService' })
    }
  }
  const wards = PLAN.map(({ id, name, kind }) => ({ id, name, kind }))
  return { wards, beds }
}
