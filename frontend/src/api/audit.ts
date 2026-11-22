import { apiDownload, apiGet } from './client'

/** One critical action in the audit trail (story 8.1). Shape of `AuditEntrySerializer` in backend/apps/audit/serializers.py. */
export interface AuditEntry {
  id: number
  /** When it happened: ISO 8601 in UTC. */
  at: string
  /** The account's email, kept even after the account is deleted. Empty for an action the system made. */
  actorEmail: string
  /** "<object>.<verb>", e.g. "bed.status_changed". */
  action: string
  /** "<app>.<model>", e.g. "hospitals.hospital". */
  targetType: string
  targetId: string
  targetRepr: string
  reason: string
  /** The values before and after the action, as the service recorded them. Null when there was none. */
  before: unknown
  after: unknown
}

/** One page of the trail (B10, #56): `count` is every match, `results` only this page, newest first. */
export interface AuditPage {
  count: number
  limit: number
  offset: number
  results: AuditEntry[]
}

/** The search filters as the page holds them. A blank one is left out of the request. */
export interface AuditFilters {
  actor: string
  action: string
  targetType: string
  targetId: string
  /** "YYYY-MM-DD", a whole day in Asia/Karachi. */
  from: string
  to: string
  /** Free text, matched against who, action, object, object id and reason. */
  text: string
}

export const EMPTY_AUDIT_FILTERS: AuditFilters = { actor: '', action: '', targetType: '', targetId: '', from: '', to: '', text: '' }

/** Rows per page on screen; the API's default and the most it returns (MAX_LIMIT on the server is 200). */
export const AUDIT_PAGE_SIZE = 50

/** An export holds at most this many rows. Over it the API answers 400 and sends no file. */
export const AUDIT_EXPORT_LIMIT = 10_000

/** The API's query names for each filter. */
const QUERY_NAME: Record<keyof AuditFilters, string> = {
  actor: 'actor',
  action: 'action',
  targetType: 'targetType',
  targetId: 'targetId',
  from: 'from',
  to: 'to',
  text: 'q',
}

function filterParams(filters: AuditFilters): URLSearchParams {
  const params = new URLSearchParams()
  for (const key of Object.keys(QUERY_NAME) as (keyof AuditFilters)[]) {
    const value = filters[key].trim()
    if (value) params.set(QUERY_NAME[key], value)
  }
  return params
}

/** One page of matching entries. GET /api/audit/entries/ (audit: view, admins only). 400 with `detail` for a bad filter. */
export function listAuditEntries(filters: AuditFilters, offset = 0): Promise<AuditPage> {
  const params = filterParams(filters)
  params.set('limit', String(AUDIT_PAGE_SIZE))
  params.set('offset', String(offset))
  return apiGet<AuditPage>(`/audit/entries/?${params}`)
}

/** The same matches as a CSV file. GET /api/audit/entries/export/. 400 with `detail` when there are over 10,000 rows. */
export async function exportAuditCsv(filters: AuditFilters): Promise<{ blob: Blob; filename: string }> {
  const { blob, filename } = await apiDownload(`/audit/entries/export/?${filterParams(filters)}`)
  return { blob, filename: filename ?? `audit-${karachiToday()}.csv` }
}

/** Today's date in the project's time zone, "YYYY-MM-DD": the name the server gives the file. */
function karachiToday(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Karachi' }).format(new Date())
}
