import { ChartFrame, TimeSeriesChart, type Point } from '../../components/charts'
import { frameState, points, tableRows, typicalFor, useMetrics } from './useMetrics'

export interface MetricLine {
  label: string
  metric: string
  /** Divide by this figure and show a percentage (e.g. occupied beds per beds in service). */
  per?: string
  color: string
  dashed?: boolean
}

type Props = {
  title: string
  summary: string
  lines: MetricLine[]
  days?: number
  bucket?: 'hour' | 'day'
  /** Draw the first line's typical day (the 14-day average by hour) as a band behind it. */
  typical?: boolean
  valueSuffix?: string
  threshold?: { value: number; label: string }
  hospital?: number
}

function ratio(top: Point[], bottom: Point[]): Point[] {
  const by = new Map(bottom.map((p) => [p.t, p.value]))
  return top.flatMap((p) => {
    const d = by.get(p.t)
    return d ? [{ t: p.t, value: Math.round((p.value / d) * 1000) / 10 }] : []
  })
}

/**
 * One or more of the hourly figures over time, as a chart with its table (B22). It loads after the page, so the
 * page's own content and actions never wait on it.
 */
export function MetricChart({ title, summary, lines, days = 1, bucket = 'hour', typical = false, valueSuffix, threshold, hospital }: Props) {
  const names = [...new Set(lines.flatMap((l) => (l.per ? [l.metric, l.per] : [l.metric])))]
  const state = useMetrics({ metrics: names, days, bucket, typical, hospital })
  const series = lines.map((l, i) => ({
    key: `${l.metric}-${i}`,
    label: l.label,
    color: l.color,
    dashed: l.dashed,
    points: l.per ? ratio(points(state.metrics, l.metric), points(state.metrics, l.per)) : points(state.metrics, l.metric),
  }))
  const band = typical && !lines[0]!.per ? typicalFor(state.metrics, lines[0]!.metric, series[0]!.points) : []
  const unit = bucket === 'hour' ? 'hour' : 'day'
  return (
    <ChartFrame
      title={title}
      summary={summary}
      legend={[
        ...lines.map((l) => ({ label: l.label, color: l.color, mark: l.dashed ? ('dashed' as const) : ('line' as const) })),
        ...(band.length ? [{ label: 'Typical day', color: 'var(--ink-muted)', mark: 'band' as const }] : []),
      ]}
      table={{
        columns: [unit === 'hour' ? 'Hour' : 'Day', ...lines.map((l) => l.label), ...(band.length ? ['Typical'] : [])],
        rows: tableRows(unit, [...series.map((s) => s.points), ...(band.length ? [band] : [])]),
      }}
      updatedAt={state.metrics ? new Date(state.metrics.updatedAt) : null}
      state={frameState(state, ...series.map((s) => s.points))}
    >
      <TimeSeriesChart
        label={summary}
        unit={unit}
        valueSuffix={valueSuffix ?? (lines[0]!.per ? '%' : '')}
        series={series}
        band={band.length ? { label: 'Typical', points: band } : undefined}
        threshold={threshold}
      />
    </ChartFrame>
  )
}
