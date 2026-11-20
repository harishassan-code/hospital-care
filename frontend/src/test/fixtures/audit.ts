import type { AuditEntry } from '../../api/audit'

const KARACHI_DAY = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Karachi' })

/** The Karachi calendar day of an ISO time, "YYYY-MM-DD". Dates in the audit filters are whole days here. */
export const karachiDay = (iso: string) => KARACHI_DAY.format(new Date(iso))

/** A few critical actions as the server records them (story 8.1): several roles, and one the system made. Times in UTC. */
export function sampleAuditEntries(now: Date): AuditEntry[] {
  const minutesAgo = (minutes: number) => new Date(now.getTime() - minutes * 60_000).toISOString()
  const entry = (id: number, minutes: number, fields: Omit<AuditEntry, 'id' | 'at'>): AuditEntry => ({ id, at: minutesAgo(minutes), ...fields })
  return [
    entry(1, 30, {
      actorEmail: 'admin@demo.test',
      action: 'hospital.updated',
      targetType: 'hospitals.hospital',
      targetId: '1',
      targetRepr: 'CityCare General Hospital',
      reason: 'Corrected the phone number',
      before: { phone: '021-111-0001' },
      after: { phone: '021-111-0002' },
    }),
    entry(2, 20, {
      actorEmail: 'nurse@demo.test',
      action: 'bed.status_changed',
      targetType: 'beds.bed',
      targetId: 'ICU-01',
      targetRepr: 'Bed ICU-01',
      reason: '',
      before: { status: 'occupied' },
      after: { status: 'reserved' },
    }),
    entry(3, 90, {
      actorEmail: 'admin@demo.test',
      action: 'user.role_changed',
      targetType: 'accounts.user',
      targetId: '4',
      targetRepr: 'nurse@demo.test',
      reason: 'Moved to the medical team',
      before: { role: 'nurse' },
      after: { role: 'doctor' },
    }),
    entry(4, 180, {
      actorEmail: '',
      action: 'blood.expired',
      targetType: 'blood.bloodunit',
      targetId: '12',
      targetRepr: 'O- red cells DN-0012',
      reason: '',
      before: { status: 'available' },
      after: { status: 'expired' },
    }),
  ]
}

/** The newest first, as the server returns them: `at` descending, then `id` descending. */
const newestFirst = (a: AuditEntry, b: AuditEntry) => b.at.localeCompare(a.at) || b.id - a.id

/**
 * The search rules of backend/apps/audit/services.py, for the mock: every filter is optional and they combine with AND.
 * A bad date, or `to` before `from`, answers `{detail}` as the 400 does.
 */
export function filterAudit(all: AuditEntry[], query: URLSearchParams): { entries: AuditEntry[] } | { detail: string } {
  const get = (key: string) => (query.get(key) ?? '').trim()
  const from = get('from')
  const to = get('to')
  for (const [key, value] of [
    ['from', from],
    ['to', to],
  ] as const) {
    if (value && !/^\d{4}-\d{2}-\d{2}$/.test(value)) return { detail: `${key} must be a date as YYYY-MM-DD.` }
  }
  if (from && to && to < from) return { detail: 'to must be the same day as from, or later.' }
  const actor = get('actor').toLowerCase()
  const action = get('action')
  const targetType = get('targetType')
  const targetId = get('targetId')
  const text = get('q').toLowerCase()
  const entries = all
    .filter((e) => !actor || e.actorEmail.toLowerCase() === actor)
    .filter((e) => !action || e.action.startsWith(action))
    .filter((e) => !targetType || e.targetType === targetType)
    .filter((e) => !targetId || e.targetId === targetId)
    .filter((e) => !from || karachiDay(e.at) >= from)
    .filter((e) => !to || karachiDay(e.at) <= to)
    .filter((e) => !text || [e.actorEmail, e.action, e.targetRepr, e.targetId, e.reason].some((v) => v.toLowerCase().includes(text)))
  return { entries: entries.sort(newestFirst) }
}

const CSV_COLUMNS = ['at', 'actorEmail', 'action', 'targetType', 'targetId', 'targetRepr', 'reason', 'before', 'after'] as const

/** The export as the server writes it: the header, then one row per entry. Only what the mock tests need is escaped. */
export function auditCsv(entries: AuditEntry[]): string {
  const cell = (value: unknown) => {
    const text = value === null || value === undefined ? '' : typeof value === 'string' ? value : JSON.stringify(value)
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  const rows = entries.map((e) => CSV_COLUMNS.map((column) => cell(e[column])))
  return [CSV_COLUMNS.join(','), ...rows.map((row) => row.join(','))].join('\r\n') + '\r\n'
}
