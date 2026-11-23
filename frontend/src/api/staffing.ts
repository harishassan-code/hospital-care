import { apiGet, apiPost } from './client'

/** Staff on duty (B22). Shapes of apps/staffing/views.py. */
export type ShiftStatus = 'onDuty' | 'late' | 'notInYet' | 'missing' | 'absent' | 'upcoming' | 'finished'
export type ShiftAction = 'clockIn' | 'markAbsent'

export interface ShiftRow {
  id: number
  name: string
  role: 'doctor' | 'nurse'
  department: string
  startsAt: string
  endsAt: string
  clockedInAt: string | null
  clockedOutAt: string | null
  status: ShiftStatus
  actions: ShiftAction[]
}

export interface Staffing {
  now: string
  summary: Record<'doctor' | 'nurse', { planned: number; onDuty: number; missing: number }>
  people: ShiftRow[]
  /** Today by hour: planned, and on duty for the hours that have begun. */
  day: { hour: number; plannedDoctors: number; plannedNurses: number; doctors?: number; nurses?: number }[]
  ratios: { department: string; patients: number; nurses: number; patientsPerNurse: number | null; target: number; short: boolean }[]
}

/** GET /api/staffing/: admin, doctor and nurse at a hospital. */
export function getStaffing(): Promise<Staffing> {
  return apiGet<Staffing>('/staffing/')
}

/** POST /api/staffing/shifts/<id>/actions/: admin and nurse. */
export function postShiftAction(id: number, action: ShiftAction): Promise<ShiftRow> {
  return apiPost<ShiftRow>(`/staffing/shifts/${id}/actions/`, { action })
}
