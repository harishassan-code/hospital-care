import { describe, expect, it } from 'vitest'
import { componentLabel, formatDay, formatMinutes } from './reports'

describe('report wording (B18)', () => {
  it.each([
    [null, '—'],
    [0, '0 min'],
    [44.6, '45 min'],
    [60, '1 h'],
    [118, '1 h 58 min'],
    [1560, '26 h'],
  ])('formats %s minutes as %s', (minutes, text) => {
    expect(formatMinutes(minutes)).toBe(text)
  })

  it('formats a calendar day without moving it', () => {
    expect(formatDay('2026-11-01')).toBe('1 Nov 2026')
    expect(formatDay('2026-12-31')).toBe('31 Dec 2026')
  })

  it('names blood components, and leaves unknown codes as they are', () => {
    expect(componentLabel('redCells')).toBe('Red cells')
    expect(componentLabel('wholeBlood')).toBe('wholeBlood')
  })
})
