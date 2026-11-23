import styles from './Charts.module.css'

export interface TimelineItem {
  start: number
  end: number
  label: string
  /** How it's drawn: booked, in progress, done or cancelled. The label always says it too. */
  tone: 'planned' | 'running' | 'done' | 'cancelled'
}

type Props = {
  rows: { label: string; items: TimelineItem[] }[]
  from: number
  to: number
  now?: number
  label: string
}

const hourFmt = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' })

/** One row per resource with its bookings across the day (B22), and a line at the current time. */
export function Timeline({ rows, from, to, now, label }: Props) {
  const span = to - from
  const pos = (t: number) => `${Math.min(100, Math.max(0, ((t - from) / span) * 100))}%`
  const hours: number[] = []
  for (let t = from; t <= to; t += 2 * 3_600_000) hours.push(t)
  return (
    <div className={styles.timeline} role="group" aria-label={label}>
      <div className={styles.timelineScale} aria-hidden="true">
        {hours.map((t) => (
          <span key={t} style={{ left: pos(t) }}>
            {hourFmt.format(t)}
          </span>
        ))}
      </div>
      {rows.map((row) => (
        <div key={row.label} className={styles.timelineRow}>
          <span className={styles.timelineLabel}>{row.label}</span>
          <span className={styles.timelineTrack}>
            {row.items.map((item) => (
              <span
                key={`${item.start}-${item.label}`}
                className={`${styles.timelineItem} ${styles[item.tone]}`}
                style={{ left: pos(item.start), width: `calc(${pos(item.end)} - ${pos(item.start)})` }}
                title={`${hourFmt.format(item.start)}–${hourFmt.format(item.end)} ${item.label}`}
              >
                <span className={styles.timelineText}>{item.label}</span>
              </span>
            ))}
            {now !== undefined && now >= from && now <= to && <span className={styles.now} style={{ left: pos(now) }} />}
          </span>
        </div>
      ))}
    </div>
  )
}
