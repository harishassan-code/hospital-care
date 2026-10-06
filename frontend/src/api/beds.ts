import { apiGet, apiPost } from './client'

export type BedStatus = 'occupied' | 'reserved' | 'cleaning' | 'free' | 'outOfService'
export type Isolation = 'contact' | 'droplet' | 'airborne'
export type WardId = 'icu' | 'hdu' | 'medA' | 'surgB' | 'paeds' | 'maternity' | 'isolation'

export interface Ward {
  id: WardId
  name: string
  /** What kind of care the ward gives, e.g. "Intensive care". */
  kind: string
}

/** Only what a bed board needs: no names, so the board can be shown on a ward screen. */
export interface Patient {
  initials: string
  age: number
  sex: 'F' | 'M'
}

export interface Bed {
  id: string
  ward: WardId
  label: string
  status: BedStatus
  /** ISO time the bed entered its current status. */
  statusSince: string
  patient?: Patient
  admittedAt?: string
  /** Local calendar date "YYYY-MM-DD". */
  expectedDischarge?: string
  isolation?: Isolation
}

export interface BedBoard {
  wards: Ward[]
  beds: Bed[]
}

export type BedAction = 'discharge' | 'markReady' | 'reserve' | 'cancelReservation' | 'outOfService' | 'returnToService'

/** Every ward and bed. GET /api/beds/ (beds: view). */
export function getBedBoard(): Promise<BedBoard> {
  return apiGet<BedBoard>('/beds/')
}

/** Apply a lifecycle action; returns the bed as saved. 409 if the move isn't allowed any more. */
export function postBedAction(bedId: string, action: BedAction): Promise<Bed> {
  return apiPost<Bed>(`/beds/${encodeURIComponent(bedId)}/actions/`, { action })
}
