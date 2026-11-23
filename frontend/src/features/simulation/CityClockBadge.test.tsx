import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { observeClock, resetClock } from '../../lib/cityClock'
import { CityClockBadge } from './CityClockBadge'

afterEach(() => resetClock())

describe('simulated time indicator (B21)', () => {
  it('stays hidden on the real clock', () => {
    render(<CityClockBadge />)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('says the time is simulated, and how, while the city runs its own clock', () => {
    render(<CityClockBadge />)
    act(() =>
      observeClock(new Headers({ 'X-City-Time': new Date().toISOString(), 'X-City-Mode': 'live', 'X-City-Speed': '10' })),
    )
    expect(screen.getByRole('status')).toHaveTextContent(/^Simulated time, 10× · /)
    act(() => observeClock(new Headers({ 'X-City-Time': new Date().toISOString(), 'X-City-Mode': 'paused', 'X-City-Speed': '10' })))
    expect(screen.getByRole('status')).toHaveTextContent(/^Simulated time, paused · /)
  })
})
