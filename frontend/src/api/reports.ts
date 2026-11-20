import { apiDownload, apiGet } from './client'

/** One row of a count by severity or status: every choice is listed, with 0 for those that didn't occur. */
export interface ReportCount {
  id: string
  label: string
  count: number
}

/** Fulfilment time for a group of cases, in minutes. Null figures when the group has no cases. */
export interface FulfilmentStats {
  count: number
  medianMinutes: number | null
  averageMinutes: number | null
  p90Minutes: number | null
}

/**
 * The three operational reports for one date range (B18, #66). Shape of `apps.reports.services.build`:
 * see docs/architecture/api.md#operational-reports-b18-66-67.
 */
export interface Report {
  range: { from: string; to: string; days: number }
  hospital: { id: number; name: string } | null
  generatedAt: string
  requests: {
    total: number
    allocations: number
    bySeverity: ReportCount[]
    byStatus: ReportCount[]
    byResourceType: { id: string; label: string; needs: number; unitsAsked: number; unitsAllocated: number }[]
  }
  fulfilment: {
    overall: FulfilmentStats
    bySeverity: (FulfilmentStats & { id: string; label: string })[]
    notFulfilled: ReportCount[]
  }
  wastage: {
    expired: number
    discarded: number
    rows: { hospital: string; group: string; component: string; expired: number; discarded: number }[]
  }
}

/** The range and hospital as the page holds them. Blank dates let the server choose (the last 30 days). */
export interface ReportFilters {
  /** "YYYY-MM-DD", a whole day in Asia/Karachi. */
  from: string
  to: string
  /** A hospital id, or "" for the whole network. */
  hospital: string
}

export type ReportFormat = 'csv' | 'pdf'

/** A report covers at most this many days; the server refuses a longer range with 400. */
export const REPORT_MAX_DAYS = 366

function filterParams(filters: ReportFilters): URLSearchParams {
  const params = new URLSearchParams()
  for (const key of ['from', 'to', 'hospital'] as const) {
    const value = filters[key].trim()
    if (value) params.set(key, value)
  }
  return params
}

/** GET /api/reports/ (reports: view, admins only). 400 with `detail` for a bad range. */
export function getReport(filters: ReportFilters): Promise<Report> {
  return apiGet<Report>(`/reports/?${filterParams(filters)}`)
}

/** The same report as a CSV or PDF file. GET /api/reports/export/; the server audit-logs each export. */
export async function exportReport(filters: ReportFilters, format: ReportFormat): Promise<{ blob: Blob; filename: string }> {
  const params = filterParams(filters)
  params.set('format', format)
  const { blob, filename } = await apiDownload(`/reports/export/?${params}`)
  // The server's name, or the same name built here when the header can't be read (a cross-origin API in local dev).
  const range = filters.from && filters.to ? `-${filters.from}-to-${filters.to}` : ''
  return { blob, filename: filename ?? `reports${range}.${format}` }
}
