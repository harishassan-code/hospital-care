/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { BLOOD_GROUPS, type BloodGroup, type BloodUnit } from '../../api/blood'
import { at, minutesFrom } from '../../test/clock'
import { availableCounts, compatibleDonors, sortFefo, stockLevel } from './blood'

describe('red-cell compatibility', () => {
  // Donor red cells must carry no ABO antigen the recipient lacks; Rh− recipients get Rh− only.
  const expected: Record<BloodGroup, BloodGroup[]> = {
    'O-': ['O-'],
    'O+': ['O-', 'O+'],
    'A-': ['O-', 'A-'],
    'A+': ['O-', 'O+', 'A-', 'A+'],
    'B-': ['O-', 'B-'],
    'B+': ['O-', 'O+', 'B-', 'B+'],
    'AB-': ['O-', 'A-', 'B-', 'AB-'],
    'AB+': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],
  }
  it.each(Object.entries(expected))('recipient %s', (recipient, donors) => {
    expect(compatibleDonors(recipient as BloodGroup, 'redCells')).toEqual(donors)
  })
})

describe('plasma compatibility', () => {
  // Donor plasma must not carry antibodies against the recipient's ABO antigens; Rh doesn't matter.
  const all: BloodGroup[] = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
  const expected: Record<string, BloodGroup[]> = {
    O: all,
    A: ['A-', 'A+', 'AB-', 'AB+'],
    B: ['B-', 'B+', 'AB-', 'AB+'],
    AB: ['AB-', 'AB+'],
  }
  it.each(Object.entries(expected))('recipient %s (either Rh)', (abo, donors) => {
    expect(compatibleDonors(`${abo}-` as BloodGroup, 'plasma')).toEqual(donors)
    expect(compatibleDonors(`${abo}+` as BloodGroup, 'plasma')).toEqual(donors)
  })
})

describe('backend rules file matches compatibleDonors', () => {
  // The backend loads the same rules from backend/apps/matching/blood_compatibility.json. Red cells and plasma
  // must agree with compatibleDonors() for every recipient, so the two copies can't drift apart silently.
  type Entry = string | { group: string; rhFlag?: boolean }
  // npm test runs from frontend/, so the path is relative to that directory.
  const file = resolve(process.cwd(), '../backend/apps/matching/blood_compatibility.json')
  const rules = JSON.parse(readFileSync(file, 'utf8')) as { components: Record<string, Record<string, Entry[]>> }
  const groupOf = (entry: Entry) => (typeof entry === 'string' ? entry : entry.group)

  for (const component of ['redCells', 'plasma'] as const) {
    it.each(BLOOD_GROUPS)(`${component} donors for recipient %s`, (recipient) => {
      const fromFile = rules.components[component][recipient].map(groupOf)
      expect(new Set(fromFile)).toEqual(new Set(compatibleDonors(recipient, component)))
    })
  }
})

describe('stock', () => {
  it('rates stock against the minimum: low below it, critical below half', () => {
    expect(stockLevel(6, 6)).toBe('ok')
    expect(stockLevel(5, 6)).toBe('low')
    expect(stockLevel(3, 6)).toBe('low')
    expect(stockLevel(2, 6)).toBe('critical')
    expect(stockLevel(0, 0)).toBe('ok')
  })

  const now = at('10:00')
  const unit = (id: string, overrides: Partial<BloodUnit>): BloodUnit => ({
    id,
    group: 'O+',
    component: 'redCells',
    collectedAt: minutesFrom(now, -60 * 24 * 10),
    expiresAt: minutesFrom(now, 60 * 24 * 30),
    status: 'available',
    location: 'Blood fridge 1',
    ...overrides,
  })

  it('counts only available units, by component and group', () => {
    const counts = availableCounts([
      unit('a', {}),
      unit('b', {}),
      unit('c', { status: 'reserved' }),
      unit('d', { group: 'AB-', component: 'plasma' }),
    ])
    expect(counts.redCells['O+']).toBe(2)
    expect(counts.plasma['AB-']).toBe(1)
    expect(counts.platelets['O+']).toBe(0)
  })

  it('orders units first-expiry-first-out', () => {
    const units = [
      unit('late', { expiresAt: minutesFrom(now, 600) }),
      unit('soon', { expiresAt: minutesFrom(now, 60) }),
      unit('mid', { expiresAt: minutesFrom(now, 300) }),
    ]
    expect(sortFefo(units).map((u) => u.id)).toEqual(['soon', 'mid', 'late'])
  })

  it('sorts by actual time, whatever the timestamp format the server sends', () => {
    const units = [
      unit('b', { expiresAt: '2026-10-07T15:00:00+05:00' }),
      unit('a', { expiresAt: '2026-10-07T14:59:59.912345+05:00' }),
      unit('c', { expiresAt: '2026-10-07T10:30:00.5+00:00' }),
    ]
    expect(sortFefo(units).map((u) => u.id)).toEqual(['a', 'b', 'c'])
  })
})
