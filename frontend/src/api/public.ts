import type { BedType } from './beds'
import type { BloodGroup } from './blood'
import { apiGet } from './client'

/** An emergency department's public status (B19). */
export type ErStatus = 'accepting' | 'busy' | 'diverting'

export const ER_STATUS_LABEL: Record<ErStatus, string> = {
  accepting: 'Accepting patients',
  busy: 'Very busy',
  diverting: 'Not accepting ambulances',
}

/** Beds of one type, as the public sees them: never exact stock. */
export type BedLevel = 'available' | 'limited' | 'full'
/** Red cells of one group across the network, against the minimum the hospitals keep. */
export type BloodLevel = 'ok' | 'low' | 'critical'

export const BED_LEVEL_LABEL: Record<BedLevel, string> = { available: 'Available', limited: 'Limited', full: 'Full' }
export const BLOOD_LEVEL_LABEL: Record<BloodLevel, string> = { ok: 'OK', low: 'Low', critical: 'Critical' }

export interface EmergencyNow {
  status: ErStatus
  waitMinutes: number
  waitingCount: number
  /** ISO timestamp of the hospital's last update */
  updatedAt: string
}

export interface BedAvailability {
  bedType: BedType
  level: BedLevel
}

/** The city at a glance. GET /api/public/network/. */
export interface NetworkSnapshot {
  updatedAt: string
  /** Active member hospitals */
  hospitals: number
  emergency: Record<ErStatus, number> & {
    notReported: number
    /** The shortest wait at a department that takes ambulances; null when none has reported. */
    shortestWait: { hospitalId: number; name: string; waitMinutes: number } | null
  }
  beds: BedAvailability[]
  blood: { group: BloodGroup; level: BloodLevel }[]
  ambulances: { available: number; total: number }
}

/** A member hospital in the directory. GET /api/public/hospitals/. */
export interface PublicHospital {
  id: number
  name: string
  type: 'hospital' | 'bloodBank'
  address: string
  latitude: number
  longitude: number
  phone: string
  services: string[]
  /** null until the hospital reports its emergency status */
  emergency: EmergencyNow | null
}

/** One hospital's public page. GET /api/public/hospitals/<id>/. */
export interface PublicHospitalDetail extends PublicHospital {
  departments: string[]
  beds: BedAvailability[]
  /** Specialists on call now, by specialty. `names` only for signed-in hospital staff (#122). */
  onDuty: { specialty: string; count: number; names: string[] | null }[]
  namesShown: boolean
}

export function getNetwork(): Promise<NetworkSnapshot> {
  return apiGet<NetworkSnapshot>('/public/network/')
}

export function listPublicHospitals(): Promise<PublicHospital[]> {
  return apiGet<PublicHospital[]>('/public/hospitals/')
}

export function getPublicHospital(id: number | string): Promise<PublicHospitalDetail> {
  return apiGet<PublicHospitalDetail>(`/public/hospitals/${id}/`)
}
