import { describe, expect, it } from 'vitest'
import { sampleCommandCentre } from '../../test/fixtures/commandCentre'
import { levelWords, nearExpiryWords, shortageLines, shortageWords } from './rules'

describe('levelWords', () => {
  it('says the level, the count and the minimum in words', () => {
    expect(levelWords({ group: 'A-', available: 1, minimum: 4, level: 'critical' })).toBe('Critical: 1 unit, minimum 4')
    expect(levelWords({ group: 'A-', available: 3, minimum: 4, level: 'low' })).toBe('Low: 3 units, minimum 4')
    expect(levelWords({ group: 'A-', available: 0, minimum: 4, level: 'critical' })).toBe('Critical: 0 units, minimum 4')
  })

  it('gives the count and the minimum when there is no shortage', () => {
    expect(levelWords({ group: 'A-', available: 6, minimum: 4, level: 'ok' })).toBe('6 units, minimum 4')
  })
})

describe('nearExpiryWords', () => {
  it('counts the units in words, with the window in days', () => {
    expect(nearExpiryWords(2, 3)).toBe('2 units expire within 3 days')
    expect(nearExpiryWords(1, 3)).toBe('1 unit expires within 3 days')
    expect(nearExpiryWords(1, 1)).toBe('1 unit expires within 1 day')
  })

  it('says so when nothing is near expiry', () => {
    expect(nearExpiryWords(0, 3)).toBe('No units expire within 3 days')
  })
})

describe('shortageWords', () => {
  it('lists the short groups with their level in words', () => {
    expect(
      shortageWords([
        { group: 'O-', level: 'critical' },
        { group: 'O+', level: 'low' },
        { group: 'A+', level: 'ok' },
      ]),
    ).toBe('Short: O− critical, O+ low')
  })

  it('says "No shortages" when every group is at or above its minimum', () => {
    expect(shortageWords([{ group: 'O-', level: 'ok' }])).toBe('No shortages')
    expect(shortageWords([])).toBe('No shortages')
  })
})

describe('shortageLines', () => {
  it('gives one line per short group, with how many hospitals are critical and how many are low', () => {
    const { hospitals } = sampleCommandCentre(new Date('2026-11-18T10:00:00Z'))
    expect(shortageLines(hospitals)).toEqual([
      'O− red cells: 1 hospital critical',
      'O+ red cells: 1 hospital low',
      'A− red cells: 1 hospital critical',
      'B+ red cells: 1 hospital critical',
      'AB− red cells: 1 hospital low',
    ])
  })

  it('leaves out groups with no shortage anywhere, and says so when there are none', () => {
    const { hospitals } = sampleCommandCentre(new Date('2026-11-18T10:00:00Z'))
    const clean = hospitals.slice(1)
    expect(shortageLines(clean)).toEqual([])
  })

  it('counts several hospitals in words', () => {
    const { hospitals } = sampleCommandCentre(new Date('2026-11-18T10:00:00Z'))
    const twice = [hospitals[0]!, { ...hospitals[0]!, id: 9, name: 'Copy' }]
    expect(shortageLines(twice)[0]).toBe('O− red cells: 2 hospitals critical')
  })
})
