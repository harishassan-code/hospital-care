import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import styles from './Charts.module.css'
import { useWidth } from './useWidth'

export interface Point {
  /** Time in milliseconds. */
  t: number
  value: number
}

export interface Series {
  key: string
  label: string
  color: string
  points: Point[]
  dashed?: boolean
}

type Props = {
  series: Series[]
  /** A shaded band behind the lines: the typical value at each time (e.g. the 14-day average by hour). */
  band?: { label: string; points: Point[] }
  /** A horizontal line with its word, e.g. "Low stock". */
  threshold?: { value: number; label: string }
  /** How the time axis reads: hours of a day, or days. */
  unit: 'hour' | 'day'
  /** The value's unit in the tooltip, e.g. "patients" or "min". */
  valueSuffix?: string
  height?: number
  /** A label for the chart as a whole (screen readers). */
  label: string
}

const PAD = { top: 12, right: 12, bottom: 26, left: 40 }
const hourFmt = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' })
const dayFmt = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', weekday: 'short', day: 'numeric' })

function niceMax(value: number): number {
  if (value <= 0) return 1
  const step = 10 ** Math.floor(Math.log10(value))
  for (const m of [1, 2, 2.5, 5, 10]) if (m * step >= value) return m * step
  return 10 * step
}

/**
 * Lines over time (B22), with an optional "typical" band and threshold line. Hover or focus it and use the arrow
 * keys to read each point; a crosshair and a tooltip show every series at that time.
 */
export function TimeSeriesChart({ series, band, threshold, unit, valueSuffix = '', height = 200, label }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const width = useWidth(ref)
  const [active, setActive] = useState<number | null>(null)

  const times = useMemo(() => {
    const all = new Set<number>()
    for (const s of series) for (const p of s.points) all.add(p.t)
    for (const p of band?.points ?? []) all.add(p.t)
    return [...all].sort((a, b) => a - b)
  }, [series, band])

  if (times.length === 0) return null
  const values = [
    ...series.flatMap((s) => s.points.map((p) => p.value)),
    ...(band?.points.map((p) => p.value) ?? []),
    threshold?.value ?? 0,
  ]
  const max = niceMax(Math.max(...values) * 1.08)
  const t0 = times[0]!
  const t1 = times[times.length - 1]!
  const innerW = Math.max(10, width - PAD.left - PAD.right)
  const innerH = height - PAD.top - PAD.bottom
  const x = (t: number) => PAD.left + (t1 === t0 ? innerW / 2 : ((t - t0) / (t1 - t0)) * innerW)
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH
  const path = (points: Point[]) => points.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p.value).toFixed(1)}`).join('')
  const ticks = [0, max / 2, max]
  const fmt = unit === 'hour' ? hourFmt : dayFmt
  const xTicks = times.length <= 8 ? times : times.filter((_, i) => i % Math.ceil(times.length / 6) === 0)

  const at = active === null ? null : times[active]!
  const valueAt = (points: Point[]) => points.find((p) => p.t === at)?.value

  function onMove(event: PointerEvent<SVGRectElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    const fraction = (event.clientX - box.left) / box.width
    const target = t0 + fraction * (t1 - t0)
    let best = 0
    for (let i = 1; i < times.length; i++) if (Math.abs(times[i]! - target) < Math.abs(times[best]! - target)) best = i
    setActive(best)
  }

  function onKey(event: KeyboardEvent) {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault()
      const step = event.key === 'ArrowRight' ? 1 : -1
      setActive((i) => Math.min(times.length - 1, Math.max(0, (i ?? (step > 0 ? -1 : times.length)) + step)))
    } else if (event.key === 'Escape') setActive(null)
  }

  const tooltip =
    at === null
      ? ''
      : [
          fmt.format(at),
          ...series.map((s) => {
            const v = valueAt(s.points)
            return v === undefined ? null : `${s.label}: ${round(v)}${valueSuffix ? ` ${valueSuffix}` : ''}`
          }),
          band && valueAt(band.points) !== undefined ? `${band.label}: ${round(valueAt(band.points)!)}` : null,
        ]
          .filter(Boolean)
          .join(' · ')

  return (
    <div ref={ref} className={styles.plot}>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={label}
        tabIndex={0}
        className={styles.svg}
        onKeyDown={onKey}
        onBlur={() => setActive(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} className={styles.grid} />
            <text x={PAD.left - 6} y={y(t) + 4} className={styles.axis} textAnchor="end">
              {round(t)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={x(t)} y={height - 8} className={styles.axis} textAnchor="middle">
            {fmt.format(t)}
          </text>
        ))}
        {band && band.points.length > 1 && (
          <path
            d={`${path(band.points)}L${x(band.points[band.points.length - 1]!.t)},${y(0)}L${x(band.points[0]!.t)},${y(0)}Z`}
            className={styles.band}
          />
        )}
        {threshold && (
          <g>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(threshold.value)} y2={y(threshold.value)} className={styles.threshold} />
            <text x={width - PAD.right} y={y(threshold.value) - 4} textAnchor="end" className={styles.thresholdText}>
              {threshold.label}
            </text>
          </g>
        )}
        {series.map((s) => (
          <g key={s.key} style={{ color: s.color }}>
            <path d={path(s.points)} className={s.dashed ? styles.dashedLine : styles.line} />
            {s.points.length === 1 && <circle cx={x(s.points[0]!.t)} cy={y(s.points[0]!.value)} r={4} className={styles.dot} />}
          </g>
        ))}
        {at !== null && (
          <g>
            <line x1={x(at)} x2={x(at)} y1={PAD.top} y2={PAD.top + innerH} className={styles.crosshair} />
            {series.map((s) => {
              const v = valueAt(s.points)
              return v === undefined ? null : (
                <circle key={s.key} cx={x(at)} cy={y(v)} r={4.5} className={styles.dot} style={{ color: s.color }} />
              )
            })}
          </g>
        )}
        <rect
          x={PAD.left}
          y={PAD.top}
          width={innerW}
          height={innerH}
          fill="transparent"
          onPointerMove={onMove}
          onPointerLeave={() => setActive(null)}
        />
      </svg>
      {at !== null && (
        <p
          className={styles.tooltip}
          style={{ left: Math.min(Math.max(x(at), 90), width - 90) }}
          role="status"
          aria-live="polite"
        >
          {tooltip}
        </p>
      )}
    </div>
  )
}

function round(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(value < 10 ? 1 : 0)
}
