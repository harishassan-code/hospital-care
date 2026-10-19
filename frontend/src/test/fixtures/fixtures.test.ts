import { describe, expect, it } from 'vitest'
import { BLOOD_GROUPS, COMPONENTS } from '../../api/blood'
import { at } from '../clock'
import { sampleBedBoard } from './beds'
import { sampleBloodUnits } from './blood'

const now = at('15:00')

describe('sample blood units', () => {
  const units = sampleBloodUnits(now)

  it('is deterministic for a given clock and seed', () => {
    expect(sampleBloodUnits(now)).toEqual(units)
  })

  it('produces valid, uniquely numbered units', () => {
    expect(units).toHaveLength(320)
    expect(new Set(units.map((u) => u.id)).size).toBe(units.length)
    for (const unit of units) {
      expect(BLOOD_GROUPS).toContain(unit.group)
      expect(COMPONENTS.map((c) => c.id)).toContain(unit.component)
      expect(unit.id).toMatch(/^G7731 26 \d{6}$/)
    }
  })

  it('marks units past their expiry as expired, and only those', () => {
    for (const unit of units) {
      expect(unit.status === 'expired').toBe(new Date(unit.expiresAt) <= now)
    }
  })
})

describe('sample bed board', () => {
  const { wards, beds } = sampleBedBoard(now)

  it('puts every bed in a known ward with a unique label', () => {
    expect(new Set(beds.map((b) => b.id)).size).toBe(beds.length)
    for (const bed of beds) expect(wards.map((w) => w.id)).toContain(bed.ward)
  })

  it('gives occupied beds a patient and no one else', () => {
    for (const bed of beds) expect(Boolean(bed.patient)).toBe(bed.status === 'occupied')
  })
})
