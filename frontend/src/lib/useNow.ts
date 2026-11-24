import { useEffect, useState } from 'react'
import { cityNow, useCityClock } from './cityClock'

/** The current time on the city clock (B21), refreshed every minute so "In now" and the now-marker stay
 * correct, and at once when the clock is paused, sped up or fast-forwarded. */
export function useNow(intervalMs = 60_000): Date {
  const clock = useCityClock()
  const [now, setNow] = useState(() => cityNow())
  const [seen, setSeen] = useState(clock)
  if (seen !== clock) {
    setSeen(clock)
    setNow(cityNow())
  }
  useEffect(() => {
    // A fast clock moves the minute hand faster: refresh as often as a city minute passes, at most every second.
    const every = clock.enabled && clock.mode === 'live' ? Math.max(1000, intervalMs / clock.speed) : intervalMs
    const id = setInterval(() => setNow(cityNow()), every)
    return () => clearInterval(id)
  }, [intervalMs, clock])
  return now
}
