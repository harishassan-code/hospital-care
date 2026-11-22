import { apiPost } from './client'

/** Where a trip stands (story #51). The names match TRIP_LIFECYCLE in backend/apps/ambulances/models.py. */
export type TripStatus = 'dispatched' | 'enRoute' | 'arrived' | 'completed'

/** A step of a trip. `depart` is "Mark departed", `arrive` is "Mark arrived", `complete` is "Mark completed". */
export type TripAction = 'depart' | 'arrive' | 'complete'

export const TRIP_STATUS_LABEL: Record<TripStatus, string> = {
  dispatched: 'Dispatched',
  enRoute: 'En route',
  arrived: 'Arrived',
  completed: 'Completed',
}

export const TRIP_ACTION_LABEL: Record<TripAction, string> = {
  depart: 'Mark departed',
  arrive: 'Mark arrived',
  complete: 'Mark completed',
}

/**
 * One ambulance carrying one approved transfer from its supplier to its receiver (story #51). Shape of `TripSerializer` in
 * backend/apps/ambulances/serializers.py. `actions` are the steps the signed-in user may take now.
 */
export interface Trip {
  id: number
  transferId: number
  status: TripStatus
  ambulance: { id: number; identifier: string; type: string }
  /** Estimated minutes from the supplier to the receiver, set when the ambulance was dispatched. */
  etaMinutes: number
  /** The person who dispatched it, or their email if they have no name. */
  dispatchedBy: string
  dispatchedAt: string
  departedAt: string | null
  arrivedAt: string | null
  completedAt: string | null
  actions: TripAction[]
}

/** Send an available ambulance from the supplying hospital to carry an approved transfer. POST /api/transfers/<id>/trips/. */
export function dispatchAmbulance(transferId: number, ambulanceId: number): Promise<Trip> {
  return apiPost<Trip>(`/transfers/${transferId}/trips/`, { ambulance: ambulanceId })
}

/** Make one step of a trip. POST /api/trips/<id>/actions/ (ambulances: edit at the supplier). 409 when the step isn't allowed now. */
export function postTripAction(id: number, action: TripAction): Promise<Trip> {
  return apiPost<Trip>(`/trips/${id}/actions/`, { action })
}
