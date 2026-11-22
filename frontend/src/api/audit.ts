import { API_URL, apiGet } from './client'

/** One audit entry (story #56). Shape of row_data in backend/apps/audit/views.py. */
export interface AuditEntry {
  id: number
  at: string
  actor: string
  action: string
  targetType: string
  targetId: string
  target: string
  reason: string
  before: unknown
  after: unknown
}

export interface AuditPage {
  count: number
  page: number
  pageSize: number
  results: AuditEntry[]
}

export interface AuditFilters {
  actor?: string
  action?: string
  targetType?: string
  from?: string
  to?: string
  q?: string
}

export function auditQuery(filters: AuditFilters, page = 1): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value)
  if (page > 1) query.set('page', String(page))
  return query.toString()
}

/** GET /api/audit/ (audit: view, admins only). */
export function getAudit(filters: AuditFilters, page = 1): Promise<AuditPage> {
  const q = auditQuery(filters, page)
  return apiGet<AuditPage>(`/audit/${q ? `?${q}` : ''}`)
}

/** Where the browser downloads the CSV with the same filters (the session cookie signs it). */
export function auditExportUrl(filters: AuditFilters): string {
  const q = auditQuery(filters)
  return `${API_URL}/audit/export.csv${q ? `?${q}` : ''}`
}
