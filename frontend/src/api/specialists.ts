import { apiDelete, apiGet, apiPatch, apiPost } from './client'

export interface SpecialistHospital {
  id: number
  name: string
}

/** A specialist as the list shows them. GET /api/specialists/ (specialists: view). */
export interface SpecialistSummary {
  id: number
  name: string
  specialty: string
  /** False once the profile is deactivated. It stays in the list, marked, and is never on call. */
  isActive: boolean
  hospital: SpecialistHospital
  /** On call at the server's clock right now. */
  onCallNow: boolean
  /** When the window covering now ends, ISO with the hospital's offset. Null when not on call. */
  onCallUntil: string | null
}

/** One stretch of on-call time. Times carry the hospital's offset, e.g. "2030-01-15T20:00:00+05:00". */
export interface OnCallWindow {
  id: number
  startsAt: string
  endsAt: string
}

/** One specialist with the on-call windows that haven't ended yet, earliest first. */
export interface SpecialistDetail extends SpecialistSummary {
  onCall: OnCallWindow[]
}

/** What a new specialist takes. The hospital is set here and can't change afterwards. */
export interface SpecialistInput {
  name: string
  specialty: string
  hospitalId: number
}

/** What a profile change takes. Only the fields given are changed. */
export interface SpecialistChanges {
  name?: string
  specialty?: string
  isActive?: boolean
}

/** The list filters the server supports. The staff page filters by hospital and specialty in the browser. */
export interface SpecialistFilters {
  hospital?: number
  specialty?: string
  availableNow?: boolean
}

/** The specialists in the network, by hospital, then specialty, then name. Only the filters given are sent. */
export function getSpecialists(filters: SpecialistFilters = {}): Promise<SpecialistSummary[]> {
  const query = new URLSearchParams()
  if (filters.hospital !== undefined) query.set('hospital', String(filters.hospital))
  if (filters.specialty) query.set('specialty', filters.specialty)
  if (filters.availableNow) query.set('availableNow', 'true')
  const search = query.toString()
  return apiGet<SpecialistSummary[]>(`/specialists/${search ? `?${search}` : ''}`)
}

/** One specialist with their upcoming on-call windows. GET /api/specialists/<id>/ (specialists: view). */
export function getSpecialist(id: number): Promise<SpecialistDetail> {
  return apiGet<SpecialistDetail>(`/specialists/${id}/`)
}

/** List a specialist. POST /api/specialists/ (specialists: edit). 400 with field errors, 403 at another hospital. */
export function createSpecialist(input: SpecialistInput): Promise<SpecialistDetail> {
  return apiPost<SpecialistDetail>('/specialists/', input)
}

/** Change a profile. PATCH /api/specialists/<id>/ (specialists: edit). */
export function updateSpecialist(id: number, changes: SpecialistChanges): Promise<SpecialistDetail> {
  return apiPatch<SpecialistDetail>(`/specialists/${id}/`, changes)
}

/** Add an on-call window. POST /api/specialists/<id>/on-call/ (specialists: edit). 400 for an overlap or a past end. */
export function addOnCallWindow(id: number, window: Pick<OnCallWindow, 'startsAt' | 'endsAt'>): Promise<OnCallWindow> {
  return apiPost<OnCallWindow>(`/specialists/${id}/on-call/`, window)
}

/** Remove a window that hasn't started. DELETE /api/specialists/<id>/on-call/<window>/. 409 once it has started. */
export function removeOnCallWindow(id: number, windowId: number): Promise<void> {
  return apiDelete(`/specialists/${id}/on-call/${windowId}/`)
}
