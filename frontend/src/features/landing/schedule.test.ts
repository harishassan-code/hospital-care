import { describe, expect, it } from 'vitest'
import type { Doctor } from '../../api/publicStatus'
import { departmentsOf, formatClock, isInNow, shiftSegments, sortForDisplay, toMinutes } from './schedule'

const at = (hhmm: string) => {
  const date = new Date(2026, 9, 5)
  date.setHours(Number(hhmm.slice(0, 2)), Number(hhmm.slice(3)))
  return date
}

const doc = (id: string, department: string, start: string, end: string): Doctor => ({
  id,
  name: `Dr ${id}`,
  department,
  start,
  end,
})

describe('schedule', () => {
  it('converts HH:MM to minutes since midnight', () => {
    expect(toMinutes('09:30')).toBe(570)
  })

  it('keeps a day shift as one segment', () => {
    expect(shiftSegments('09:00', '13:00')).toEqual([[540, 780]])
  })

  it('splits an overnight shift at midnight', () => {
    expect(shiftSegments('20:00', '08:00')).toEqual([
      [1200, 1440],
      [0, 480],
    ])
  })

  it('knows who is in now, including overnight shifts', () => {
    const day = doc('a', 'Cardiology', '09:00', '13:00')
    const night = doc('b', 'Emergency medicine', '20:00', '08:00')
    expect(isInNow(day, at('10:00'))).toBe(true)
    expect(isInNow(day, at('13:00'))).toBe(false)
    expect(isInNow(night, at('23:00'))).toBe(true)
    expect(isInNow(night, at('07:59'))).toBe(true)
    expect(isInNow(night, at('12:00'))).toBe(false)
  })

  it('lists each department once, sorted', () => {
    const doctors = [
      doc('a', 'Paediatrics', '09:00', '10:00'),
      doc('b', 'Cardiology', '09:00', '10:00'),
      doc('c', 'Paediatrics', '11:00', '12:00'),
    ]
    expect(departmentsOf(doctors)).toEqual(['Cardiology', 'Paediatrics'])
  })

  it('formats a clock time as 24-hour HH:MM', () => {
    expect(formatClock(at('07:05'))).toBe('07:05')
    expect(formatClock(at('22:40'))).toBe('22:40')
  })

  it('puts doctors who are in first, then orders by start time', () => {
    const doctors = [doc('late', 'X', '16:00', '20:00'), doc('early', 'X', '06:00', '09:00'), doc('now', 'X', '09:00', '13:00')]
    expect(sortForDisplay(doctors, at('10:00')).map((d) => d.id)).toEqual(['now', 'early', 'late'])
  })
})
