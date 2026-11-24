import { useEffect } from 'react'
import { tickSimulation } from '../../api/simulation'
import { useCityClock } from '../../lib/cityClock'

const TICK_MS = 20_000

/**
 * Keeps the city running while someone has the site open (B21): Vercel runs nothing in the background, so every
 * open page asks the API to bring the city up to its clock every 20 seconds. The API runs at most one tick every
 * 15 seconds, however many pages ask. Nothing happens until the API says it runs a city clock.
 */
export function CityTicker() {
  const { enabled, mode } = useCityClock()
  useEffect(() => {
    if (!enabled || mode === 'paused') return
    const tick = () => {
      if (document.visibilityState !== 'hidden') void tickSimulation().catch(() => undefined)
    }
    tick()
    const id = setInterval(tick, TICK_MS)
    return () => clearInterval(id)
  }, [enabled, mode])
  return null
}
