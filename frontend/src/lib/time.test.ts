import { describe, expect, it } from 'vitest'
import {
  currentShift,
  dateKey,
  formatClock,
  formatDuration,
  formatShortDate,
  fromDateKey,
  hoursUntil,
  isInNow,
  shiftSegments,
  toMinutes,
} from './time'
import { at, minutesFrom } from '../test/clock'

describe('clock maths', () => {
  it('converts HH:MM to minutes since midnight', () => {
    expect(toMinutes('09:30')).toBe(570)
  })

  it('formats a clock time as 24-hour HH:MM', () => {
    expect(formatClock(at('07:05'))).toBe('07:05')
    expect(formatClock(at('22:40'))).toBe('22:40')
  })

  it('keeps a day range as one segment and splits overnight ranges at midnight', () => {
    expect(shiftSegments('09:00', '13:00')).toEqual([[540, 780]])
    expect(shiftSegments('20:00', '08:00')).toEqual([
      [1200, 1440],
      [0, 480],
    ])
  })

  it('knows whether now falls inside a range, including overnight', () => {
    expect(isInNow({ start: '09:00', end: '13:00' }, at('10:00'))).toBe(true)
    expect(isInNow({ start: '09:00', end: '13:00' }, at('13:00'))).toBe(false)
    expect(isInNow({ start: '20:00', end: '08:00' }, at('23:00'))).toBe(true)
    expect(isInNow({ start: '20:00', end: '08:00' }, at('07:59'))).toBe(true)
    expect(isInNow({ start: '20:00', end: '08:00' }, at('12:00'))).toBe(false)
  })
})

describe('currentShift', () => {
  const shifts = [
    { name: 'Morning', start: '08:00', end: '14:00' },
    { name: 'Evening', start: '14:00', end: '20:00' },
    { name: 'Night', start: '20:00', end: '08:00' },
  ]

  it('finds the shift and the minutes left in it', () => {
    expect(currentShift(shifts, at('10:30'))).toEqual({ ...shifts[0], minutesLeft: 210 })
    expect(currentShift(shifts, at('14:00'))).toEqual({ ...shifts[1], minutesLeft: 360 })
  })

  it('handles the overnight shift on both sides of midnight', () => {
    expect(currentShift(shifts, at('23:00')).minutesLeft).toBe(540)
    expect(currentShift(shifts, at('02:00'))).toEqual({ ...shifts[2], minutesLeft: 360 })
  })
})

describe('formatDuration', () => {
  it('uses minutes, hours or days as appropriate', () => {
    expect(formatDuration(52)).toBe('52 min')
    expect(formatDuration(60)).toBe('1 h')
    expect(formatDuration(192)).toBe('3 h 12 min')
    expect(formatDuration(60 * 24 * 4 + 60 * 6)).toBe('4 d 6 h')
    expect(formatDuration(-5)).toBe('0 min')
  })
})

describe('hoursUntil', () => {
  it('measures hours from now to a timestamp, negative when past', () => {
    const now = at('10:00')
    expect(hoursUntil(minutesFrom(now, 90), now)).toBe(1.5)
    expect(hoursUntil(minutesFrom(now, -60), now)).toBe(-1)
  })
})

describe('dateKey', () => {
  it('gives the local calendar date as YYYY-MM-DD', () => {
    expect(dateKey(at('00:05'))).toBe('2026-10-05')
    expect(dateKey(at('23:59'))).toBe('2026-10-05')
  })
})

describe('fromDateKey / formatShortDate', () => {
  it('reads a YYYY-MM-DD key as local midnight', () => {
    const date = fromDateKey('2026-11-15')
    expect([date.getFullYear(), date.getMonth(), date.getDate(), date.getHours()]).toEqual([2026, 10, 15, 0])
  })

  it('formats short dates, optionally with the year', () => {
    expect(formatShortDate(fromDateKey('2026-11-15'))).toBe('15 Nov')
    expect(formatShortDate(fromDateKey('2026-11-15'), { year: true })).toBe('15 Nov 2026')
  })
})
