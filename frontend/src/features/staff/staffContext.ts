import { createContext, useContext } from 'react'
import type { Bed, Ward } from '../../api/beds'
import type { BloodUnit } from '../../api/blood'
import type { Medicine } from '../../api/pharmacy'
import type { PublicStatus } from '../../api/publicStatus'
import type { BedAction } from '../beds/beds'
import type { AttentionItem } from './attention'
import type { Role } from './roles'

export interface StaffData {
  wards: Ward[]
  beds: Bed[]
  units: BloodUnit[]
  medicines: Medicine[]
  emergency: PublicStatus['emergency']
}

export interface StaffState {
  role: Role
  setRole: (role: Role) => void
  now: Date
  /** null while loading. */
  data: StaffData | null
  failed: boolean
  /** Attention items for the modules this role can see. */
  attention: AttentionItem[]
  updateBed: (bedId: string, action: BedAction) => void
}

export const StaffContext = createContext<StaffState | null>(null)

export function useStaff(): StaffState {
  const state = useContext(StaffContext)
  if (!state) throw new Error('useStaff must be used inside <StaffProvider>')
  return state
}
