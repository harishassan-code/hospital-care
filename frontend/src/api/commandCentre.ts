import type { BloodGroup } from './blood'
import { apiGet } from './client'

/** One hospital's row on the command centre (story #55). Shape of network_snapshot in apps/core/command_centre.py. */
export interface HospitalSnapshot {
  id: number
  name: string
  beds: { free: number; total: number }
  icu: { free: number; total: number }
  redCells: Record<BloodGroup, number>
  nearExpiry: number
  equipment: { available: number; total: number }
  emergencies: Partial<Record<'critical' | 'high' | 'moderate' | 'low', number>>
}

export interface Shortage {
  hospital: string
  kind: 'blood' | 'icu'
  level: 'low' | 'critical'
  group?: BloodGroup
  count?: number
  minimum?: number
}

export interface NetworkSnapshot {
  totals: {
    hospitals: number
    freeBeds: number
    freeIcu: number
    redCells: number
    nearExpiry: number
    activeEmergencies: number
  }
  hospitals: HospitalSnapshot[]
  shortages: Shortage[]
}

/** GET /api/command-centre/ (commandCentre: view, admins only). */
export function getNetworkSnapshot(): Promise<NetworkSnapshot> {
  return apiGet<NetworkSnapshot>('/command-centre/')
}
