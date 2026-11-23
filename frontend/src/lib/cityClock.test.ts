import { afterEach, describe, expect, it, vi } from 'vitest'
import { cityNow, clockState, isSimulatedTime, observeClock, resetClock } from './cityClock'

afterEach(() => {
  resetClock()
  vi.useRealTimers()
})

const headers = (time: string, mode = 'live', speed = '1') =>
  new Headers({ 'X-City-Time': time, 'X-City-Mode': mode, 'X-City-Speed': speed })

describe('city clock (B21)', () => {
  it('is the device clock until the API sends one', () => {
    vi.useFakeTimers({ now: new Date('2026-11-23T09:00:00Z') })
    observeClock(new Headers())
    expect(cityNow().toISOString()).toBe('2026-11-23T09:00:00.000Z')
  })

  it('runs on from the last response at its speed', () => {
    vi.useFakeTimers({ now: new Date('2026-11-23T09:00:00Z') })
    observeClock(headers('2026-11-25T12:00:00Z', 'live', '10'))
    vi.advanceTimersByTime(60_000)
    expect(cityNow().toISOString()).toBe('2026-11-25T12:10:00.000Z')
  })

  it('stands still while paused or fast-forwarding', () => {
    vi.useFakeTimers({ now: new Date('2026-11-23T09:00:00Z') })
    observeClock(headers('2026-11-25T12:00:00Z', 'paused'))
    vi.advanceTimersByTime(600_000)
    expect(cityNow().toISOString()).toBe('2026-11-25T12:00:00.000Z')
  })

  it('counts as simulated when it is faster, paused or moved ahead, not when it is the real time', () => {
    vi.useFakeTimers({ now: new Date('2026-11-23T09:00:00Z') })
    observeClock(headers('2026-11-23T09:00:00Z'))
    expect(isSimulatedTime(clockState())).toBe(false)
    observeClock(headers('2026-11-23T09:00:00Z', 'live', '5'))
    expect(isSimulatedTime(clockState())).toBe(true)
    observeClock(headers('2026-11-30T09:00:00Z'))
    expect(isSimulatedTime(clockState())).toBe(true)
  })
})

