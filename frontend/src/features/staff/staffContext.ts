import { createContext, useContext } from 'react'
import type { User } from '../../api/auth'
import type { Bed, BedAction, Ward } from '../../api/beds'
import type { BloodUnit } from '../../api/blood'
import type { Medicine } from '../../api/pharmacy'
import type { PublicStatus } from '../../api/publicStatus'
import type { AttentionItem } from './attention'
import type { Role } from './roles'

/** Everything the staff pages show. Modules the role can't see are left empty. */
export interface StaffData {
  wards: Ward[]
  beds: Bed[]
  units: BloodUnit[]
  medicines: Medicine[]
  /** null if the public ER status couldn't be loaded; the rest of the workspace still works. */
  emergency: PublicStatus['emergency'] | null
}

export type BedActionResult = { ok: true } | { ok: false; message: string }

export interface StaffState {
  user: User
  role: Role
  now: Date
  /** null while loading. */
  data: StaffData | null
  failed: boolean
  /** Attention items for the modules this role can see. */
  attention: AttentionItem[]
  /** Saves a bed status change on the server, then shows the bed as saved. */
  updateBed: (bedId: string, action: BedAction) => Promise<BedActionResult>
  signOut: () => Promise<void>
}

export const StaffContext = createContext<StaffState | null>(null)

export function useStaff(): StaffState {
  const state = useContext(StaffContext)
  if (!state) throw new Error('useStaff must be used inside <StaffProvider>')
  return state
}
