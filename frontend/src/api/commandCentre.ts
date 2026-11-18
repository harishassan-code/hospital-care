import type { BedType } from './beds'
import type { BloodGroup, Component } from './blood'
import type { EquipmentType } from './equipment'
import type { ResourceType } from './emergencies'
import { apiGet } from './client'

/** "ok" at or above the red-cell minimum, "low" below it, "critical" below half of it. Judged by the server. */
export type ShortageLevel = 'ok' | 'low' | 'critical'

export interface RedCellFigure {
  group: BloodGroup
  available: number
  minimum: number
  level: ShortageLevel
}

export interface ComponentFigure {
  /** Available and not past expiry. */
  usable: number
  /** The usable ones expiring within `nearExpiryDays`. */
  nearExpiry: number
}

export interface CaseFigure {
  /** Open, matching, partially fulfilled or escalated. */
  active: number
  escalated: number
}

/** One hospital's figures, or the network's totals (which carry no levels). */
export interface Figures<Red> {
  redCells: Red[]
  components: Record<Component, ComponentFigure>
  beds: Record<BedType, number>
  equipment: Record<EquipmentType, number>
  operatingRooms: number
  cases: CaseFigure
  /** Quantity less fulfilled less held, summed over the active cases, by resource type. */
  open: Record<ResourceType, number>
}

export interface HospitalFigures extends Figures<RedCellFigure> {
  id: number
  name: string
}

/** Network totals: sums of the hospital rows. Counts only, so no level is worked out from them. */
export type NetworkTotals = Figures<{ group: BloodGroup; available: number }>

/** Shape of `CommandCentreSerializer`'s output in backend/apps/command_centre/services.py (story #55). */
export interface CommandCentre {
  updatedAt: string
  nearExpiryDays: number
  totals: NetworkTotals
  /** Hospitals with a critical red-cell group first, then by name. Active hospitals only. */
  hospitals: HospitalFigures[]
}

/** Every figure on the command centre page, in one read. GET /api/command-centre/ (commandCentre: view, admin only). */
export function getCommandCentre(): Promise<CommandCentre> {
  return apiGet<CommandCentre>('/command-centre/')
}
