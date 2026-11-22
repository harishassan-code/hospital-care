import type { BloodGroup, BloodUnit } from './blood'
import { apiGet, apiPost } from './client'

/** Mirrors BLOOD_APPOINTMENT_SLOT_MINUTES in backend settings (default 30). The API only sends the slot length
 * with an existing appointment, so the page can't read it first. */
export const DONOR_SLOT_MINUTES = 30

/** The start times the page offers, inclusive, every DONOR_SLOT_MINUTES. The API has no opening hours, so this window
 * is a page choice (B11, question 3). The server still accepts any slot boundary. */
export const DONOR_FIRST_SLOT = '08:00'
export const DONOR_LAST_SLOT = '17:00'

/** A donor (stories #20, #21). Shape of `DonorSerializer` in backend/apps/blood/serializers.py. */
export interface Donor {
  /** The donor code, e.g. DNR-00042. The server sets it. */
  id: string
  fullName: string
  bloodGroup: BloodGroup
  phone: string
  email: string
  /** When the donor last gave blood, or null. */
  lastDonationAt: string | null
  eligible: boolean
  /** Why the donor isn't eligible. Empty when eligible. */
  ineligibleReason: string
  /** First day (YYYY-MM-DD) the donor can give again. Null when eligible, or for a deferral with no end date. */
  eligibleFrom: string | null
  /** The hospital the donor belongs to. Null for a donor an admin registered with no hospital. */
  hospitalId: number | null
}

/** The donor's panel view: the donor plus their units. GET /api/blood/donors/<code>/ */
export interface DonorDetail extends Donor {
  units: BloodUnit[]
}

/** A donation appointment (story #22). Shape of `AppointmentSerializer`. */
export interface Appointment {
  id: number
  donorId: string
  donorName: string
  /** ISO timestamp on a slot boundary. */
  startsAt: string
  slotMinutes: number
  status: 'booked' | 'cancelled'
  hospitalId: number | null
}

export interface DonorInput {
  fullName: string
  bloodGroup: BloodGroup
  phone?: string
  email?: string
}

export interface ScreeningInput {
  eligible: boolean
  reason?: string
  /** "YYYY-MM-DD", or null for a deferral with no end date. */
  deferredUntil?: string | null
}

/** Donors at the user's hospital (admins: all), at most 200. GET /api/blood/donors/?q=&bloodGroup= (donors: view). */
export function listDonors(filter: { q?: string; bloodGroup?: BloodGroup } = {}): Promise<Donor[]> {
  const query = new URLSearchParams()
  if (filter.q) query.set('q', filter.q)
  if (filter.bloodGroup) query.set('bloodGroup', filter.bloodGroup)
  const text = query.toString()
  return apiGet<Donor[]>(`/blood/donors/${text ? `?${text}` : ''}`)
}

/** POST /api/blood/donors/ (donors: edit). The server sets the code and the hospital. */
export function registerDonor(input: DonorInput): Promise<Donor> {
  return apiPost<Donor>('/blood/donors/', input)
}

/** GET /api/blood/donors/<code>/ (donors: view). */
export function getDonor(code: string): Promise<DonorDetail> {
  return apiGet<DonorDetail>(`/blood/donors/${encodeURIComponent(code)}/`)
}

/** POST /api/blood/donors/<code>/screening/ (donors: edit). Returns the donor as the server now has it. */
export function recordScreening(code: string, input: ScreeningInput): Promise<Donor> {
  return apiPost<Donor>(`/blood/donors/${encodeURIComponent(code)}/screening/`, input)
}

/** Upcoming booked appointments at the user's hospital (admins: all). GET /api/blood/appointments/ (donors: view). */
export function listAppointments(): Promise<Appointment[]> {
  return apiGet<Appointment[]>('/blood/appointments/')
}

/** POST /api/blood/appointments/ (donors: edit). 201 with the booking; 400 for a taken slot or an ineligible donor. */
export function bookAppointment(input: { donorId: string; startsAt: string }): Promise<Appointment> {
  return apiPost<Appointment>('/blood/appointments/', input)
}

/** POST /api/blood/appointments/<id>/cancel/ (donors: edit). 409 if already cancelled. */
export function cancelAppointment(id: number): Promise<Appointment> {
  return apiPost<Appointment>(`/blood/appointments/${id}/cancel/`, undefined)
}
