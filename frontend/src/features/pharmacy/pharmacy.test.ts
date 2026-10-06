import { describe, expect, it } from 'vitest'
import type { Medicine } from '../../api/pharmacy'
import { at } from '../../test/clock'
import { daysOfSupply, daysUntil, filterMedicines, nearestExpiry, needsReorder, onHand } from './pharmacy'

const now = at('10:00') // 5 Oct 2026

const med = (overrides: Partial<Medicine>): Medicine => ({
  id: 'm1',
  name: 'Paracetamol',
  strength: '500 mg',
  form: 'Tablet',
  category: 'Analgesic',
  unit: 'tablets',
  reorderLevel: 500,
  dailyUse: 200,
  location: 'Main store A1',
  highAlert: false,
  controlled: false,
  batches: [
    { number: 'P-2401', expiresOn: '2027-03-01', quantity: 1200 },
    { number: 'P-2310', expiresOn: '2026-11-15', quantity: 300 },
  ],
  ...overrides,
})

describe('stock maths', () => {
  it('adds up every batch', () => {
    expect(onHand(med({}))).toBe(1500)
  })

  it('works out days of supply from average daily use, to one decimal', () => {
    expect(daysOfSupply(med({ dailyUse: 400 }))).toBe(3.8)
    expect(daysOfSupply(med({ dailyUse: 0 }))).toBe(Infinity)
  })

  it('needs a reorder at or below the reorder level', () => {
    expect(needsReorder(med({ reorderLevel: 1500 }))).toBe(true)
    expect(needsReorder(med({ reorderLevel: 1499 }))).toBe(false)
  })

  it('finds the batch that expires first, skipping empty batches', () => {
    const m = med({ batches: [...med({}).batches, { number: 'P-2205', expiresOn: '2026-10-10', quantity: 0 }] })
    expect(nearestExpiry(m)?.number).toBe('P-2310')
    expect(nearestExpiry(med({ batches: [] }))).toBeUndefined()
  })

  it('counts whole days until a date', () => {
    expect(daysUntil('2026-10-05', now)).toBe(0)
    expect(daysUntil('2026-11-15', now)).toBe(41)
    expect(daysUntil('2026-10-01', now)).toBe(-4)
  })
})

describe('filterMedicines', () => {
  const list = [
    med({ id: 'para' }),
    med({
      id: 'insulin',
      name: 'Insulin glargine',
      category: 'Antidiabetic',
      highAlert: true,
      reorderLevel: 2000,
      batches: [{ number: 'I-1', expiresOn: '2027-06-01', quantity: 1500 }],
    }),
    med({ id: 'morphine', name: 'Morphine', category: 'Opioid analgesic', highAlert: true, controlled: true }),
    med({ id: 'old', name: 'Ceftriaxone', batches: [{ number: 'C-1', expiresOn: '2026-12-01', quantity: 50 }] }),
  ]
  const ids = (filter: Parameters<typeof filterMedicines>[1], query = '') =>
    filterMedicines(list, filter, query, now).map((m) => m.id)

  it('filters by flag', () => {
    expect(ids('all')).toEqual(['para', 'insulin', 'morphine', 'old'])
    expect(ids('reorder')).toEqual(['insulin', 'old'])
    expect(ids('highAlert')).toEqual(['insulin', 'morphine'])
    expect(ids('controlled')).toEqual(['morphine'])
    expect(ids('expiring')).toEqual(['para', 'morphine', 'old'])
  })

  it('searches name and category, ignoring case', () => {
    expect(ids('all', 'INSUL')).toEqual(['insulin'])
    expect(ids('all', 'opioid')).toEqual(['morphine'])
  })
})
