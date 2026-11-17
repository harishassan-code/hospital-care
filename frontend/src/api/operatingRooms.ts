import { apiGet, apiPost } from './client'

/** Asia/Karachi (the hospitals' time zone) is UTC+5 all year, with no daylight saving. Bookings are sent with it. */
export const HOSPITAL_UTC_OFFSET = '+05:00'

export type OrCapability = 'general' | 'cardiac' | 'trauma' | 'neuro' | 'orthopedic' | 'obstetric' | 'pediatric'
export type OrStatus = 'available' | 'reserved' | 'inUse' | 'cleaning' | 'maintenance' | 'outOfService'

export const OR_CAPABILITIES: readonly { value: OrCapability; label: string }[] = [
  { value: 'general', label: 'General' },
  { value: 'cardiac', label: 'Cardiac' },
  { value: 'trauma', label: 'Trauma' },
  { value: 'neuro', label: 'Neuro' },
  { value: 'orthopedic', label: 'Orthopedic' },
  { value: 'obstetric', label: 'Obstetric' },
  { value: 'pediatric', label: 'Pediatric' },
]

export const OR_STATUSES: readonly { value: OrStatus; label: string }[] = [
  { value: 'available', label: 'Available' },
  { value: 'reserved', label: 'Reserved' },
  { value: 'inUse', label: 'In use' },
  { value: 'cleaning', label: 'Cleaning' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'outOfService', label: 'Out of service' },
]

/** One operating room and what it is equipped for (story #28). */
export interface OperatingRoom {
  id: number
  name: string
  capabilities: OrCapability[]
  location: string
  status: OrStatus
  statusSince: string
  hospital: string | null
}

export type OperatingRoomInput = Pick<OperatingRoom, 'name' | 'capabilities' | 'location' | 'status'>

export type OperatingRoomFilters = { capability?: OrCapability; status?: OrStatus }

/** The rooms in the user's hospital, optionally filtered. GET /api/operating-rooms/ (operatingRooms: view). */
export function getOperatingRooms(filters: OperatingRoomFilters = {}): Promise<OperatingRoom[]> {
  const query = new URLSearchParams()
  if (filters.capability) query.set('capability', filters.capability)
  if (filters.status) query.set('status', filters.status)
  const search = query.toString()
  return apiGet<OperatingRoom[]>(`/operating-rooms/${search ? `?${search}` : ''}`)
}

/** Register a room. POST /api/operating-rooms/ (operatingRooms: edit). 400 with field errors, e.g. a taken name. */
export function createOperatingRoom(input: OperatingRoomInput): Promise<OperatingRoom> {
  return apiPost<OperatingRoom>('/operating-rooms/', input)
}

export type OperatingRoomAction =
  | 'startCase'
  | 'reserve'
  | 'cancelReservation'
  | 'finishCase'
  | 'finishCleaning'
  | 'startMaintenance'
  | 'finishMaintenance'
  | 'outOfService'
  | 'returnToService'

/** Move a room along its lifecycle. POST /api/operating-rooms/<id>/actions/ (operatingRooms: edit). 409 if the move isn't allowed any more. */
export function postOperatingRoomAction(id: number, action: OperatingRoomAction): Promise<OperatingRoom> {
  return apiPost<OperatingRoom>(`/operating-rooms/${id}/actions/`, { action })
}

/** One booked slot in a room, from GET /api/operating-rooms/schedule/ or POST /api/operating-rooms/bookings/ (story #29). */
export interface OrBooking {
  id: number
  roomId: number
  startsAt: string
  endsAt: string
  procedure: string
  surgeon: string
  patientInitials: string
  status: 'booked' | 'cancelled'
  bookedBy: string
  /** Whether the signed-in user may cancel it: admins and nurses any, others only their own. */
  canCancel: boolean
}

/** A room and its booked slots on one day. */
export interface ScheduleRoom {
  id: number
  name: string
  status: OrStatus
  capabilities: OrCapability[]
  bookings: OrBooking[]
}

export interface OperatingRoomSchedule {
  date: string
  rooms: ScheduleRoom[]
}

/** What a booking takes. Times carry HOSPITAL_UTC_OFFSET, e.g. "2030-01-15T09:00+05:00". */
export interface OrBookingInput {
  roomId: number
  startsAt: string
  endsAt: string
  procedure: string
  surgeon: string
  patientInitials: string
}

/** Every room with that day's bookings, "YYYY-MM-DD". GET /api/operating-rooms/schedule/ (operatingRooms: view). */
export function getOperatingRoomSchedule(date: string): Promise<OperatingRoomSchedule> {
  return apiGet<OperatingRoomSchedule>(`/operating-rooms/schedule/?date=${encodeURIComponent(date)}`)
}

/** Book a slot. POST /api/operating-rooms/bookings/ (orBookings: edit). 400 with field errors, e.g. an overlap. */
export function createOrBooking(input: OrBookingInput): Promise<OrBooking> {
  return apiPost<OrBooking>('/operating-rooms/bookings/', input)
}

/** Cancel a booking. POST /api/operating-rooms/bookings/<id>/cancel/ (orBookings: edit). 409 if already cancelled. */
export function cancelOrBooking(id: number): Promise<OrBooking> {
  return apiPost<OrBooking>(`/operating-rooms/bookings/${id}/cancel/`, undefined)
}
