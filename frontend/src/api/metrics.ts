import { apiGet } from './client'

/** The hourly figures behind the trend charts (B22). Shape of apps/metrics/read.py. */
export interface MetricPoint {
  /** An ISO time (by hour) or date (by day). */
  at: string
  value: number
}

export interface Metrics {
  from: string
  to: string
  bucket: 'hour' | 'day'
  series: Record<string, MetricPoint[]>
  /** Each figure's average by hour of the day over the last 14 days, when asked for. */
  typical?: Record<string, { hour: number; value: number }[]>
  updatedAt: string
}

export interface MetricsQuery {
  metrics: string[]
  days?: number
  bucket?: 'hour' | 'day'
  typical?: boolean
  hospital?: number
  perHospital?: boolean
}

/** GET /api/metrics/: own hospital; the whole network (or one hospital, or each apart) for the CityCare admin. */
export function getMetrics(query: MetricsQuery): Promise<Metrics> {
  const params = new URLSearchParams({ metrics: query.metrics.join(',') })
  if (query.days) params.set('days', String(query.days))
  if (query.bucket) params.set('bucket', query.bucket)
  if (query.typical) params.set('typical', 'true')
  if (query.hospital !== undefined) params.set('hospital', String(query.hospital))
  if (query.perHospital) params.set('perHospital', 'true')
  return apiGet<Metrics>(`/metrics/?${params}`)
}
