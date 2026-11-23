import styles from './Charts.module.css'

export interface BarSegment {
  key: string
  label: string
  value: number
  color: string
}

export interface Bar {
  label: string
  /** One segment for a plain bar; several for a stacked one. */
  segments: BarSegment[]
  /** Shown at the end of the bar instead of the total, e.g. "12 · 3 below the line". */
  note?: string
  /** A word for a bar that needs attention (e.g. "Low"), shown with it: never colour alone. */
  flag?: string
}

type Props = {
  bars: Bar[]
  /** A line across every bar at this value, with its word, e.g. the low-stock level. */
  threshold?: { value: number; label: string }
  /** Per-bar lines instead of one (e.g. each blood group's own minimum). */
  thresholds?: number[]
  max?: number
  label: string
}

/**
 * Horizontal bars, plain or stacked (B22), each with its figure written at the end, and an optional threshold
 * line. Hovering a segment names it; the frame's table gives every figure.
 */
export function BarChart({ bars, threshold, thresholds, max, label }: Props) {
  const totals = bars.map((b) => b.segments.reduce((sum, s) => sum + s.value, 0))
  const top = max ?? Math.max(1, ...totals, threshold?.value ?? 0, ...(thresholds ?? []))
  const pct = (v: number) => `${Math.min(100, (v / top) * 100)}%`
  return (
    <ul className={styles.bars} aria-label={label}>
      {bars.map((bar, i) => {
        const line = thresholds?.[i] ?? threshold?.value
        return (
          <li key={bar.label} className={styles.barRow}>
            <span className={styles.barLabel}>{bar.label}</span>
            <span className={styles.track}>
              {bar.segments
                .filter((s) => s.value > 0)
                .map((s) => (
                  <span
                    key={s.key}
                    className={styles.segment}
                    style={{ width: pct(s.value), background: s.color }}
                    title={`${s.label}: ${s.value}`}
                  />
                ))}
              {line !== undefined && (
                <span className={styles.barLine} style={{ left: pct(line) }} title={threshold?.label ?? `Line: ${line}`} />
              )}
            </span>
            <span className={styles.barValue}>
              {bar.note ?? totals[i]}
              {bar.flag && <span className={styles.flag}>{bar.flag}</span>}
            </span>
          </li>
        )
      })}
      {threshold && (
        <li className={styles.barKey} aria-hidden="true">
          <span className={styles.barLineKey} /> {threshold.label}
        </li>
      )}
    </ul>
  )
}
