import { apiGet, apiPost } from './client'

export type AmbulanceType = 'basic' | 'advanced' | 'patientTransport'
/** `dispatched` ("On trip") is set and cleared only by trips (story #51); the registry's own moves can't make it. */
export type AmbulanceStatus = 'available' | 'dispatched' | 'maintenance' | 'outOfService'

export const AMBULANCE_TYPES: readonly { value: AmbulanceType; label: string }[] = [
  { value: 'basic', label: 'Basic life support' },
  { value: 'advanced', label: 'Advanced life support' },
  { value: 'patientTransport', label: 'Patient transport' },
]

export const AMBULANCE_STATUSES: readonly { value: AmbulanceStatus; label: string }[] = [
  { value: 'available', label: 'Available' },
  { value: 'dispatched', label: 'On trip' },
  { value: 'maintenance', label: 'In maintenance' },
  { value: 'outOfService', label: 'Out of service' },
]

/** The trip on the road with an ambulance, if any (story #51). */
export interface AmbulanceTrip {
  id: number
  status: 'dispatched' | 'enRoute' | 'arrived'
  /** The transfer it carries. */
  transferId: number
}

/** One ambulance and its base hospital (story #50), and the trip it is on, if any (story #51). */
export interface Ambulance {
  id: number
  identifier: string
  type: AmbulanceType
  status: AmbulanceStatus
  statusSince: string
  hospital: string | null
  trip: AmbulanceTrip | null
}

/** What the register form sends. Admins pick the base hospital; everyone else registers at their own. */
export interface AmbulanceInput {
  identifier: string
  type: AmbulanceType
  hospitalId?: number
}

export interface AmbulanceFilter {
  status?: AmbulanceStatus
  /** A hospital id: only the ambulances based there (admins only see other hospitals' ambulances). */
  hospitalId?: number
}

/**
 * The ambulances in the user's hospital (all of them for admins), filtered. GET /api/ambulances/ (ambulances: view).
 */
export function getAmbulances(filter: AmbulanceFilter = {}): Promise<Ambulance[]> {
  const query = new URLSearchParams()
  if (filter.status) query.set('status', filter.status)
  if (filter.hospitalId !== undefined) query.set('hospital', String(filter.hospitalId))
  const search = query.toString()
  return apiGet<Ambulance[]>(`/ambulances/${search ? `?${search}` : ''}`)
}

/** Register an ambulance. POST /api/ambulances/ (ambulances: edit). 400 with field errors, e.g. a taken asset tag. */
export function createAmbulance(input: AmbulanceInput): Promise<Ambulance> {
  return apiPost<Ambulance>('/ambulances/', input)
}

export type AmbulanceAction = 'startMaintenance' | 'finishMaintenance' | 'outOfService' | 'returnToService'

/**
 * Move an ambulance along its lifecycle. POST /api/ambulances/<id>/actions/ (ambulances: edit). 409 if not allowed now,
 * and for a move a trip makes (dispatch, release), which the registry never offers.
 */
export function postAmbulanceAction(id: number, action: AmbulanceAction): Promise<Ambulance> {
  return apiPost<Ambulance>(`/ambulances/${id}/actions/`, { action })
}
