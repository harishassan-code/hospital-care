import { apiGet, apiPost } from './client'

export type AmbulanceType = 'bls' | 'als' | 'pts'
export type AmbulanceStatus = 'available' | 'onTrip' | 'maintenance' | 'outOfService'
export type AmbulanceAction = 'startMaintenance' | 'finishMaintenance' | 'outOfService' | 'returnToService'
export type TripStatus = 'dispatched' | 'enRoute' | 'arrived' | 'completed' | 'cancelled'

/** One vehicle (story #50). Shape of AmbulanceSerializer in backend/apps/ambulances/views.py. */
export interface Ambulance {
  id: number
  identifier: string
  type: AmbulanceType
  plate: string
  note: string
  status: AmbulanceStatus
  statusSince: string
  hospital: string
  hospitalId: number
}

export interface AmbulanceInput {
  identifier: string
  type: AmbulanceType
  plate: string
}

/** An ambulance carrying a transfer (story #51). */
export interface Trip {
  id: number
  ambulance: { id: number; identifier: string }
  status: TripStatus
  etaMinutes: number | null
  dispatchedAt: string
  arrivedAt: string | null
}

export const AMBULANCE_TYPES: readonly { value: AmbulanceType; label: string }[] = [
  { value: 'als', label: 'Advanced life support' },
  { value: 'bls', label: 'Basic life support' },
  { value: 'pts', label: 'Patient transport' },
]

export const AMBULANCE_STATUSES: readonly { value: AmbulanceStatus; label: string }[] = [
  { value: 'available', label: 'Available' },
  { value: 'onTrip', label: 'On trip' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'outOfService', label: 'Out of service' },
]

export const TRIP_STATUS_LABEL: Record<TripStatus, string> = {
  dispatched: 'Dispatched',
  enRoute: 'En route',
  arrived: 'Arrived',
  completed: 'Completed',
  cancelled: 'Cancelled',
}

/** The moves staff make by hand from each status; startTrip and endTrip are made only by a trip. */
export const AMBULANCE_MOVES: Record<AmbulanceStatus, { action: AmbulanceAction; label: string }[]> = {
  available: [
    { action: 'startMaintenance', label: 'Start maintenance' },
    { action: 'outOfService', label: 'Out of service' },
  ],
  onTrip: [],
  maintenance: [
    { action: 'finishMaintenance', label: 'Finish maintenance' },
    { action: 'outOfService', label: 'Out of service' },
  ],
  outOfService: [{ action: 'returnToService', label: 'Return to service' }],
}

/** The fleet at the user's hospital (admins: the network). GET /api/ambulances/ (ambulances: view). */
export function getAmbulances(): Promise<Ambulance[]> {
  return apiGet<Ambulance[]>('/ambulances/')
}

/** Available ambulances at a supplying hospital, for dispatch. GET /api/ambulances/available/ (transfers: view). */
export function getAvailableAmbulances(hospitalId: number): Promise<Ambulance[]> {
  return apiGet<Ambulance[]>(`/ambulances/available/?hospital=${hospitalId}`)
}

export function registerAmbulance(input: AmbulanceInput): Promise<Ambulance> {
  return apiPost<Ambulance>('/ambulances/', input)
}

export function postAmbulanceAction(id: number, action: AmbulanceAction): Promise<Ambulance> {
  return apiPost<Ambulance>(`/ambulances/${id}/actions/`, { action })
}

/** Send an ambulance with an approved transfer; the transfer goes to dispatched. */
export function dispatchTrip(transferId: number, ambulanceId: number): Promise<Trip> {
  return apiPost<Trip>('/ambulances/trips/', { transferId, ambulanceId })
}

export function postTripAction(tripId: number, action: 'enRoute' | 'arrive'): Promise<Trip> {
  return apiPost<Trip>(`/ambulances/trips/${tripId}/actions/`, { action })
}
