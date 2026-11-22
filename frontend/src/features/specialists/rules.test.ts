import { describe, expect, it } from 'vitest'
import type { OnCallWindow } from '../../api/specialists'
import { clashing, clashMessage, coversNow, hasStarted } from './rules'

const window = (startsAt: string, endsAt: string, id = 1): OnCallWindow => ({ id, startsAt, endsAt })
const at = (clock: string) => new Date(`2026-11-18T${clock}:00+05:00`)

describe('coversNow', () => {
  const shift = window('2026-11-18T08:00:00+05:00', '2026-11-18T20:00:00+05:00')

  it('includes the start and excludes the end', () => {
    expect(coversNow(shift, at('07:59'))).toBe(false)
    expect(coversNow(shift, at('08:00'))).toBe(true)
    expect(coversNow(shift, at('19:59'))).toBe(true)
    expect(coversNow(shift, at('20:00'))).toBe(false)
  })
})

describe('hasStarted', () => {
  const shift = window('2026-11-18T08:00:00+05:00', '2026-11-18T20:00:00+05:00')

  it('is true from the start on, so a window that has begun can’t be removed', () => {
    expect(hasStarted(shift, at('07:59'))).toBe(false)
    expect(hasStarted(shift, at('08:00'))).toBe(true)
    expect(hasStarted(shift, at('21:00'))).toBe(true)
  })
})

describe('clashing', () => {
  const windows = [window('2026-11-18T08:00:00+05:00', '2026-11-18T20:00:00+05:00')]
  const between = (start: string, end: string) =>
    clashing(windows, `2026-11-18T${start}:00+05:00`, `2026-11-18T${end}:00+05:00`)

  it('finds a window that shares any time with the new one', () => {
    expect(between('06:00', '09:00')).toBeDefined()
    expect(between('18:00', '22:00')).toBeDefined()
    expect(between('09:00', '10:00')).toBeDefined()
    expect(between('06:00', '22:00')).toBeDefined()
  })

  it('lets windows that only touch sit side by side', () => {
    expect(between('06:00', '08:00')).toBeUndefined()
    expect(between('20:00', '22:00')).toBeUndefined()
  })
})

describe('clashMessage', () => {
  it('words the overlap the way the server does', () => {
    const existing = window('2026-11-18T08:00:00+05:00', '2026-11-18T20:00:00+05:00')
    expect(clashMessage(existing)).toBe('Overlaps an on-call window from 18 Nov 08:00 to 18 Nov 20:00.')
  })
})
