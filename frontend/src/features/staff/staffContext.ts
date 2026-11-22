import { createContext, useContext } from 'react'
import type { User } from '../../api/auth'
import type { Bed, BedAction, Ward } from '../../api/beds'
import type { BloodUnit } from '../../api/blood'
import type { EmergencyCase } from '../../api/emergencies'
import type { Medicine } from '../../api/pharmacy'
import type { PublicStatus } from '../../api/publicStatus'
import type { Transfer } from '../../api/transfers'
import type { NotificationFeed } from '../notifications/useNotificationFeed'
import type { AttentionItem } from './attention'
import type { Role } from './roles'

/** The transfers the user's hospital is part of, in each direction (admins: the same network-wide list in both). */
export interface TransfersData {
  incoming: Transfer[]
  outgoing: Transfer[]
}

/** Everything the staff pages show. Modules the role can't see are left empty. */
export interface StaffData {
  wards: Ward[]
  beds: Bed[]
  units: BloodUnit[]
  medicines: Medicine[]
  /** null if the public ER status couldn't be loaded; the rest of the workspace still works. */
  emergency: PublicStatus['emergency'] | null
  /** The hospital's emergency cases. null if they couldn't be loaded. */
  cases: EmergencyCase[] | null
  /** null when the role can't see transfers, or they couldn't be loaded. */
  transfers: TransfersData | null
}

export type BedActionResult = { ok: true } | { ok: false; message: string }

export interface StaffState {
  user: User
  role: Role
  now: Date
  /** null while loading. */
  data: StaffData | null
  /** True when the first load failed. Reloads keep trying. */
  failed: boolean
  /** When the data was last loaded successfully. Null before that. */
  updatedAt: Date | null
  /** True when the last reload failed: `data` is from `updatedAt`. */
  refreshFailed: boolean
  /** Attention items for the modules this role can see. */
  attention: AttentionItem[]
  /** The user's notifications (B07, #53), polled every 30 seconds for the whole staff session. */
  notifications: NotificationFeed
  /** Saves a bed status change on the server, then shows the bed as saved. */
  updateBed: (bedId: string, action: BedAction) => Promise<BedActionResult>
  /** Adds a newly registered unit, or updates an existing one by id (e.g. after a screening result), in the loaded data. */
  upsertUnit: (unit: BloodUnit) => void
  /** Reads the blood units again, so the stock figures show what changed on the server (e.g. after an allocation). */
  refreshUnits: () => Promise<void>
  signOut: () => Promise<void>
}

export const StaffContext = createContext<StaffState | null>(null)

export function useStaff(): StaffState {
  const state = useContext(StaffContext)
  if (!state) throw new Error('useStaff must be used inside <StaffProvider>')
  return state
}
