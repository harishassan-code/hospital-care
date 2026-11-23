import { useEffect, useState } from 'react'
import { getMetrics, type Metrics, type MetricsQuery } from '../../api/metrics'
import type { Point } from '../../components/charts'

const REFRESH_MS = 60_000

export type MetricsState = { metrics: Metrics | null; failed: boolean }

/**
 * The figures for a page's charts, loaded after the page itself (the main content never waits on its charts) and
 * refreshed every minute while the tab is open. `null` query: nothing to load (e.g. the role can't see them).
 */
export function useMetrics(query: MetricsQuery | null): MetricsState {
  const [state, setState] = useState<MetricsState>({ metrics: null, failed: false })
  const key = query ? JSON.stringify(query) : ''
  useEffect(() => {
    if (!key) return
    const parsed = JSON.parse(key) as MetricsQuery
    let active = true
    const load = () =>
      getMetrics(parsed)
        .then((metrics) => active && setState({ metrics, failed: false }))
        .catch(() => active && setState((s) => ({ ...s, failed: s.metrics === null })))
    void load()
    const id = setInterval(() => {
      if (document.visibilityState !== 'hidden') void load()
    }, REFRESH_MS)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [key])
  return state
}

/** A series as chart points. Days are placed at Karachi noon so they sit in the middle of their day. */
export function points(metrics: Metrics | null, name: string): Point[] {
  return (metrics?.series[name] ?? []).map((p) => ({
    t: p.at.length === 10 ? Date.parse(`${p.at}T07:00:00Z`) : Date.parse(p.at),
    value: p.value,
  }))
}

/** The typical day laid over the same hours as `series` (each point's hour of day in Karachi). */
export function typicalFor(metrics: Metrics | null, name: string, over: Point[]): Point[] {
  const byHour = new Map((metrics?.typical?.[name] ?? []).map((p) => [p.hour, p.value]))
  const hourOf = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', hour: 'numeric', hourCycle: 'h23' })
  return over.flatMap((p) => {
    const value = byHour.get(Number(hourOf.format(p.t)))
    return value === undefined ? [] : [{ t: p.t, value }]
  })
}

/** The state a chart frame shows for these figures. */
export function frameState(state: MetricsState, ...series: Point[][]): 'loading' | 'failed' | 'empty' | 'ready' {
  if (state.failed) return 'failed'
  if (!state.metrics) return 'loading'
  return series.some((s) => s.length > 0) ? 'ready' : 'empty'
}

const hourFmt = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' })
const dayFmt = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', weekday: 'short', day: 'numeric', month: 'short' })

/** Rows for a chart's table: one per time, one column per series. */
export function tableRows(unit: 'hour' | 'day', columns: Point[][]): (string | number)[][] {
  const times = [...new Set(columns.flatMap((c) => c.map((p) => p.t)))].sort((a, b) => a - b)
  const fmt = unit === 'hour' ? hourFmt : dayFmt
  return times.map((t) => [fmt.format(t), ...columns.map((c) => c.find((p) => p.t === t)?.value ?? '–')])
}
