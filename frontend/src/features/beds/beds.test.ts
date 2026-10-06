import { describe, expect, it } from 'vitest'
import type { Bed } from '../../api/beds'
import { at, minutesFrom } from '../../test/clock'
import {
  actionsFor,
  applyAction,
  dayOfStay,
  dischargesToday,
  isCleaningOverdue,
  minutesInStatus,
  summarize,
} from './beds'

const now = at('10:00')

const bed = (overrides: Partial<Bed>): Bed => ({
  id: 'b1',
  ward: 'medA',
  label: 'MA-01',
  status: 'free',
  statusSince: minutesFrom(now, -30),
  ...overrides,
})

const occupied = bed({
  status: 'occupied',
  patient: { initials: 'S.A.', age: 54, sex: 'F' },
  admittedAt: minutesFrom(now, -60 * 30),
  expectedDischarge: '2026-10-05',
  isolation: 'contact',
})

describe('bed transitions', () => {
  it('offers only the valid next steps for each status', () => {
    const offered = (s: Bed['status']) => actionsFor(s).map((a) => a.action)
    expect(offered('occupied')).toEqual(['discharge'])
    expect(offered('cleaning')).toEqual(['markReady'])
    expect(offered('free')).toEqual(['reserve', 'outOfService'])
    expect(offered('reserved')).toEqual(['cancelReservation'])
    expect(offered('outOfService')).toEqual(['returnToService'])
  })

  it('discharging sends the bed for cleaning and clears the patient', () => {
    const next = applyAction(occupied, 'discharge', now)
    expect(next.status).toBe('cleaning')
    expect(next.statusSince).toBe(now.toISOString())
    expect(next.patient).toBeUndefined()
    expect(next.admittedAt).toBeUndefined()
    expect(next.expectedDischarge).toBeUndefined()
    expect(next.isolation).toBeUndefined()
    expect(occupied.status).toBe('occupied')
  })

  it('returning to service goes through cleaning first', () => {
    expect(applyAction(bed({ status: 'outOfService' }), 'returnToService', now).status).toBe('cleaning')
  })

  it('refuses an action that is not valid for the current status', () => {
    expect(() => applyAction(occupied, 'markReady', now)).toThrow(/can't mark ready/i)
  })
})

describe('bed timing', () => {
  it('measures minutes in the current status', () => {
    expect(minutesInStatus(bed({ statusSince: minutesFrom(now, -52) }), now)).toBe(52)
  })

  it('flags cleaning that runs past the 45-minute target', () => {
    expect(isCleaningOverdue(bed({ status: 'cleaning', statusSince: minutesFrom(now, -46) }), now)).toBe(true)
    expect(isCleaningOverdue(bed({ status: 'cleaning', statusSince: minutesFrom(now, -30) }), now)).toBe(false)
    expect(isCleaningOverdue(bed({ status: 'free', statusSince: minutesFrom(now, -90) }), now)).toBe(false)
  })

  it('counts the day of stay from admission, starting at day 1', () => {
    expect(dayOfStay(occupied, now)).toBe(2)
    expect(dayOfStay(bed({ status: 'occupied', admittedAt: minutesFrom(now, -60) }), now)).toBe(1)
  })
})

describe('bed lists', () => {
  it('counts beds by status', () => {
    const beds = [occupied, bed({ status: 'free' }), bed({ status: 'free' }), bed({ status: 'cleaning' })]
    expect(summarize(beds)).toEqual({ total: 4, occupied: 1, reserved: 0, cleaning: 1, free: 2, outOfService: 0 })
  })

  it('finds occupied beds expected to be discharged today', () => {
    const later = { ...occupied, id: 'b2', expectedDischarge: '2026-10-07' }
    expect(dischargesToday([occupied, later, bed({})], now).map((b) => b.id)).toEqual(['b1'])
  })
})
