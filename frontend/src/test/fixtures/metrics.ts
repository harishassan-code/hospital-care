import type { Metrics } from '../../api/metrics'

/** A steady shape per figure, so tests can read exact values: the hour of day plus a base per figure. */
const BASE: Record<string, number> = {
  'er.arrivals': 6,
  'er.departures': 5,
  'er.wait_minutes': 30,
  'beds.occupied': 150,
  'beds.in_service': 180,
  'blood.issued': 2,
  'blood.donated': 1,
  'ambulances.trips': 1,
  'or.in_use': 3,
  'or.rooms': 6,
  'equipment.ventilators_in_use': 4,
}

/** GET /api/metrics/ as the server answers it (B22), from the query string. */
export function sampleMetrics(query: URLSearchParams, now: Date): Metrics {
  const names = (query.get('metrics') ?? '').split(',').filter(Boolean)
  const days = Number(query.get('days') ?? '1')
  const bucket = (query.get('bucket') ?? 'hour') as 'hour' | 'day'
  const end = new Date(now)
  end.setUTCMinutes(0, 0, 0)
  const series: Metrics['series'] = {}
  for (const name of names) {
    const base = BASE[name] ?? BASE[name.split('.').slice(0, 2).join('.')] ?? 10
    if (bucket === 'day') {
      series[name] = Array.from({ length: days }, (_, i) => {
        const day = new Date(end.getTime() - (days - 1 - i) * 86_400_000).toISOString().slice(0, 10)
        return { at: day, value: base * 24 + i }
      })
    } else {
      series[name] = Array.from({ length: days * 24 }, (_, i) => ({
        at: new Date(end.getTime() - (days * 24 - 1 - i) * 3_600_000).toISOString(),
        value: base + (i % 6),
      }))
    }
  }
  const typical = query.get('typical') === 'true'
    ? Object.fromEntries(names.map((n) => [n, Array.from({ length: 24 }, (_, hour) => ({ hour, value: (BASE[n] ?? 10) + 1 }))]))
    : undefined
  return { from: end.toISOString(), to: end.toISOString(), bucket, series, typical, updatedAt: now.toISOString() }
}
