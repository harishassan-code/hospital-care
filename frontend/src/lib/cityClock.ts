import { useSyncExternalStore } from 'react'

/**
 * The city clock (B21). On staging the API runs the city on its own clock, which the CityCare admin can pause,
 * speed up or fast-forward; every response carries it (X-City-Time, X-City-Mode, X-City-Speed). Screens read
 * the time here, so "now", "today" and every countdown agree with the data. Without those headers (local
 * development, tests) it is the device's clock.
 */
export type ClockMode = 'real' | 'live' | 'paused' | 'fastForward'

export interface ClockState {
  /** True once the API has said it runs a city clock. */
  enabled: boolean
  mode: ClockMode
  speed: number
  /** City time (ms) when the last response was read, and the device time (ms) then. */
  cityAt: number
  realAt: number
}

const REAL: ClockState = { enabled: false, mode: 'real', speed: 1, cityAt: 0, realAt: 0 }
let state: ClockState = REAL
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

/** Reads the clock headers off an API response. Responses without them leave the clock as it is. */
export function observeClock(headers: Headers): void {
  const time = headers.get('X-City-Time')
  if (!time) return
  const cityAt = Date.parse(time)
  if (Number.isNaN(cityAt)) return
  const mode = (headers.get('X-City-Mode') ?? 'live') as ClockMode
  const speed = Number(headers.get('X-City-Speed') ?? '1') || 1
  const changed = !state.enabled || state.mode !== mode || state.speed !== speed
  state = { enabled: true, mode, speed, cityAt, realAt: Date.now() }
  if (changed) emit()
}

/** The city's time now. */
export function cityNow(): Date {
  if (!state.enabled) return new Date()
  if (state.mode !== 'live') return new Date(state.cityAt)
  return new Date(state.cityAt + (Date.now() - state.realAt) * state.speed)
}

/** How far the city clock is from the device's, in minutes (positive: ahead). */
export function cityOffsetMinutes(): number {
  return state.enabled ? Math.round((cityNow().getTime() - Date.now()) / 60_000) : 0
}

/** True when the city isn't simply on real time: paused, faster or slower, fast-forwarding, or moved. */
export function isSimulatedTime(clock: ClockState): boolean {
  if (!clock.enabled) return false
  return clock.mode !== 'live' || clock.speed !== 1 || Math.abs(cityOffsetMinutes()) >= 2
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** The clock's settings now. */
export function clockState(): ClockState {
  return state
}

/** The clock's mode and speed, re-rendering when they change. Use cityNow() for the time itself. */
export function useCityClock(): ClockState {
  return useSyncExternalStore(subscribe, clockState)
}

/** For tests: back to the device's clock. */
export function resetClock(): void {
  state = REAL
  emit()
}
