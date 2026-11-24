import { Clock3 } from 'lucide-react'
import { isSimulatedTime, useCityClock } from '../../lib/cityClock'
import { useNow } from '../../lib/useNow'
import styles from './CityClockBadge.module.css'

const format = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Karachi',
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})

/** Shown on every signed-in page while the city clock isn't simply the real time (B21): paused, faster or slower,
 * fast-forwarding, or moved ahead. */
export function CityClockBadge() {
  const clock = useCityClock()
  const now = useNow()
  if (!isSimulatedTime(clock)) return null
  const state =
    clock.mode === 'paused'
      ? 'paused'
      : clock.mode === 'fastForward'
        ? 'fast-forwarding'
        : clock.speed === 1
          ? ''
          : `${clock.speed === 0.5 ? '½' : clock.speed}×`
  return (
    <p className={styles.badge} role="status">
      <Clock3 size={14} aria-hidden="true" />
      <span>
        Simulated time{state ? `, ${state}` : ''} · <time dateTime={now.toISOString()}>{format.format(now)}</time>
      </span>
    </p>
  )
}
