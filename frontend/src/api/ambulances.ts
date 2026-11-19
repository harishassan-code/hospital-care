import { apiGet, apiPost } from './client'

export type AmbulanceType = 'basic' | 'advanced' | 'transport'

export type AmbulanceStatus = 'available' | 'inUse' | 'maintenance' | 'outOfService'

export type TripStatus = 'dispatched' | 'enRoute' | 'arrived' | 'completed'

export type TripAction = 'startRoute' | 'arrive' | 'complete'

export interface Ambulance {
  id: number
  identifier: string
  type: AmbulanceType
  status: AmbulanceStatus
  statusSince: string
  hospital: string
}

export interface Trip {
  id: number
  status: TripStatus
  etaMinutes: number | null
  dispatchedAt: string
  ambulance: { id: number; identifier: string; type: AmbulanceType }
  actions: TripAction[]
}

export const AMBULANCE_TYPES = [
  { value: 'basic' as const, label: 'Basic life support' },
  { value: 'advanced' as const, label: 'Advanced life support' },
  { value: 'transport' as const, label: 'Patient transport' },
]

export const AMBULANCE_STATUSES = [
  { value: 'available' as const, label: 'Available' },
  { value: 'inUse' as const, label: 'In use' },
  { value: 'maintenance' as const, label: 'Maintenance' },
  { value: 'outOfService' as const, label: 'Out of service' },
]

export const TRIP_STATUS_LABEL: Record<TripStatus, string> = {
  dispatched: 'Dispatched',
  enRoute: 'En route',
  arrived: 'Arrived',
  completed: 'Completed',
}

export const TRIP_ACTION_LABEL: Record<TripAction, string> = {
  startRoute: 'Mark en route',
  arrive: 'Mark arrived',
  complete: 'Complete trip',
}

export function getAmbulances(): Promise<Ambulance[]> {
  return apiGet<Ambulance[]>('/ambulances/')
}

export interface AmbulanceInput {
  identifier: string
  type: AmbulanceType
  status?: AmbulanceStatus
}

export function registerAmbulance(input: AmbulanceInput): Promise<Ambulance> {
  return apiPost<Ambulance>('/ambulances/', input)
}

export function dispatchTransferTrip(transferId: number, ambulanceId: number) {
  return apiPost<import('./transfers').Transfer>(`/transfers/${transferId}/trip/`, { ambulanceId })
}

export function postTripAction(tripId: number, action: TripAction) {
  return apiPost<import('./transfers').Transfer>(`/trips/${tripId}/actions/`, { action })
}