import type { BloodGroup } from './blood'
import { apiGet, apiPost } from './client'

/** A donor (story #20) with eligibility (story #21). Shape of DonorSerializer in backend/apps/blood/serializers.py. */
export interface Donor {
  id: string
  fullName: string
  bloodGroup: BloodGroup
  phone: string
  email: string
  lastDonationAt: string | null
  eligible: boolean
  ineligibleReason: string
  eligibleFrom: string | null
}

export interface DonorInput {
  fullName: string
  bloodGroup: BloodGroup
  phone: string
  email: string
}

export interface ScreeningInput {
  eligible: boolean
  reason: string
  deferredUntil: string | null
}

/** A donation appointment (story #22). */
export interface Appointment {
  id: number
  donorId: string
  donorName: string
  startsAt: string
  slotMinutes: number
  status: string
}

export function getDonors(q = ''): Promise<Donor[]> {
  return apiGet<Donor[]>(`/blood/donors/${q ? `?q=${encodeURIComponent(q)}` : ''}`)
}

export function registerDonor(input: DonorInput): Promise<Donor> {
  return apiPost<Donor>('/blood/donors/', input)
}

export function recordScreening(code: string, input: ScreeningInput): Promise<Donor> {
  return apiPost<Donor>(`/blood/donors/${encodeURIComponent(code)}/screening/`, input)
}

export function getAppointments(): Promise<Appointment[]> {
  return apiGet<Appointment[]>('/blood/appointments/')
}

export function bookAppointment(donorId: string, startsAt: string): Promise<Appointment> {
  return apiPost<Appointment>('/blood/appointments/', { donorId, startsAt })
}

export function cancelAppointment(id: number): Promise<Appointment> {
  return apiPost<Appointment>(`/blood/appointments/${id}/cancel/`, {})
}
