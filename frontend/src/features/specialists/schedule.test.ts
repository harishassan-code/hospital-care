import { describe, expect, it } from 'vitest'
import { karachiClock, karachiDate, karachiDateTime, karachiDay, karachiDayKey, karachiIso, onCallText } from './schedule'

describe('Karachi clock', () => {
  it('shows the hospital clock, whatever the viewer’s zone', () => {
    expect(karachiClock('2026-11-18T20:00:00+05:00')).toBe('20:00')
    expect(karachiClock('2026-11-18T15:00:00Z')).toBe('20:00') // the same instant, in UTC
  })

  it('writes midnight as 00:00', () => {
    expect(karachiClock('2026-11-18T19:00:00Z')).toBe('00:00')
  })

  it('words days and dates the way the server words an overlap', () => {
    expect(karachiDate('2026-11-05T08:00:00+05:00')).toBe('05 Nov')
    expect(karachiDay('2026-11-18T08:00:00+05:00')).toBe('Wed 18 Nov')
    expect(karachiDateTime('2026-11-18T20:00:00+05:00')).toBe('Wed 18 Nov 20:00')
  })

  it('counts the day in Karachi', () => {
    expect(karachiDayKey('2026-11-18T23:30:00+05:00')).toBe('2026-11-18')
    expect(karachiDayKey('2026-11-18T19:30:00Z')).toBe('2026-11-19') // 00:30 the next day in Karachi
  })
})

describe('onCallText', () => {
  const now = new Date('2026-11-18T12:00:00+05:00')

  it('says until when, and names the day only when it is not today', () => {
    expect(onCallText({ onCallNow: true, onCallUntil: '2026-11-18T20:00:00+05:00' }, now)).toBe('On call until 20:00')
    expect(onCallText({ onCallNow: true, onCallUntil: '2026-11-19T08:00:00+05:00' }, now)).toBe(
      'On call until 08:00 on Thu 19 Nov',
    )
  })

  it('says not on call when the server says so', () => {
    expect(onCallText({ onCallNow: false, onCallUntil: null }, now)).toBe('Not on call')
  })
})

describe('karachiIso', () => {
  it('joins a Karachi date and clock time with the hospital’s offset', () => {
    expect(karachiIso('2026-11-18', '08:00')).toBe('2026-11-18T08:00:00+05:00')
  })
})
