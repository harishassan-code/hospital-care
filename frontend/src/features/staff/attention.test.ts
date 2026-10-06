import { describe, expect, it } from 'vitest'
import type { Bed, Ward } from '../../api/beds'
import type { BloodUnit } from '../../api/blood'
import type { Medicine } from '../../api/pharmacy'
import { at, minutesFrom } from '../../test/clock'
import { buildAttention } from './attention'

const now = at('15:00')
const wards: Ward[] = [{ id: 'surgB', name: 'Surgical B', kind: 'General surgery' }]

const unit = (i: number, overrides: Partial<BloodUnit>): BloodUnit => ({
  id: `U${i}`,
  group: 'O+',
  component: 'redCells',
  collectedAt: minutesFrom(now, -60 * 24),
  expiresAt: minutesFrom(now, 60 * 24 * 30),
  status: 'available',
  location: 'Blood fridge 1',
  ...overrides,
})

/** Enough red cells in every group to clear the minimums, so tests only see what they add. */
const healthyStock: BloodUnit[] = (['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'] as const).flatMap((group, g) =>
  Array.from({ length: 30 }, (_, i) => unit(g * 100 + i, { group })),
)

const medicine = (overrides: Partial<Medicine>): Medicine => ({
  id: 'pcm',
  name: 'Paracetamol',
  strength: '500 mg',
  form: 'Tablet',
  category: 'Analgesic',
  unit: 'tablets',
  reorderLevel: 100,
  dailyUse: 10,
  location: 'A1',
  highAlert: false,
  controlled: false,
  batches: [{ number: 'B1', expiresOn: '2027-01-01', quantity: 1000 }],
  ...overrides,
})

const build = (parts: Partial<Parameters<typeof buildAttention>[0]>) =>
  buildAttention({ wards, beds: [], units: healthyStock, medicines: [], ...parts }, now)

describe('buildAttention', () => {
  it('is empty when everything is fine', () => {
    expect(build({ medicines: [medicine({})] })).toEqual([])
  })

  it('flags red-cell groups below minimum, critical below half', () => {
    const units = healthyStock.filter((u) => u.group !== 'O-' && u.group !== 'B-')
    const items = build({ units: [...units, unit(900, { group: 'O-' }), ...[1, 2, 3].map((i) => unit(910 + i, { group: 'B-' }))] })
    expect(items.map((i) => [i.severity, i.title])).toEqual([
      ['critical', 'O− red cells: 1 unit left'],
      ['warning', 'B− red cells: 3 units left'],
    ])
    expect(items[0]).toMatchObject({ module: 'blood', href: '/staff/blood', detail: 'Minimum 6' })
  })

  it('groups available units expiring within 24 hours by component', () => {
    const soon = [1, 2, 3].map((i) =>
      unit(800 + i, { component: 'platelets', expiresAt: minutesFrom(now, 60 * 10) }),
    )
    const items = build({ units: [...healthyStock, ...soon, unit(810, { component: 'platelets', status: 'issued', expiresAt: minutesFrom(now, 60) })] })
    expect(items.map((i) => i.title)).toEqual(['3 platelet units expire within 24 h'])
  })

  it('flags beds cleaning past the target', () => {
    const bed: Bed = { id: 'SB-12', ward: 'surgB', label: 'SB-12', status: 'cleaning', statusSince: minutesFrom(now, -52) }
    const items = build({ beds: [bed] })
    expect(items).toEqual([
      expect.objectContaining({
        severity: 'warning',
        module: 'beds',
        title: 'SB-12 cleaning for 52 min',
        detail: 'Surgical B · target 45 min',
      }),
    ])
  })

  it('flags medicines that need reordering, critical under two days of supply', () => {
    const items = build({
      medicines: [
        medicine({ id: 'a', name: 'Morphine', strength: '10 mg/mL', unit: 'ampoules', reorderLevel: 100, dailyUse: 22, batches: [{ number: 'M', expiresOn: '2027-01-01', quantity: 84 }] }),
        medicine({ id: 'b', name: 'Insulin glargine', strength: '100 units/mL', unit: 'pens', reorderLevel: 60, dailyUse: 14, batches: [{ number: 'G', expiresOn: '2027-01-01', quantity: 21 }] }),
      ],
    })
    expect(items.map((i) => [i.severity, i.title, i.detail])).toEqual([
      ['critical', 'Insulin glargine 100 units/mL: 1.5 days of supply left', '21 pens on hand · reorder level 60'],
      ['warning', 'Morphine 10 mg/mL: 3.8 days of supply left', '84 ampoules on hand · reorder level 100'],
    ])
  })
})
