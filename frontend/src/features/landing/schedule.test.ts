import { describe, expect, it } from 'vitest'
import type { Doctor } from '../../api/publicStatus'
import { at } from '../../test/clock'
import { departmentsOf, sortForDisplay } from './schedule'

const doc = (id: string, department: string, start: string, end: string): Doctor => ({
  id,
  name: `Dr ${id}`,
  department,
  start,
  end,
})

describe('doctor schedule', () => {
  it('lists each department once, sorted', () => {
    const doctors = [
      doc('a', 'Paediatrics', '09:00', '10:00'),
      doc('b', 'Cardiology', '09:00', '10:00'),
      doc('c', 'Paediatrics', '11:00', '12:00'),
    ]
    expect(departmentsOf(doctors)).toEqual(['Cardiology', 'Paediatrics'])
  })

  it('puts doctors who are in first, then orders by start time', () => {
    const doctors = [doc('late', 'X', '16:00', '20:00'), doc('early', 'X', '06:00', '09:00'), doc('now', 'X', '09:00', '13:00')]
    expect(sortForDisplay(doctors, at('10:00')).map((d) => d.id)).toEqual(['now', 'early', 'late'])
  })
})
