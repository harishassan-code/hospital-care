import { apiGet } from './client'

export type ErStatus = 'accepting' | 'busy' | 'diverting'

export interface Doctor {
  id: string
  /** null for the public: names go only to signed-in staff (#122). */
  name: string | null
  department: string
  /** "HH:MM", 24-hour clock */
  start: string
  /** "HH:MM"; earlier than start means the shift runs past midnight */
  end: string
}

export interface PublicStatus {
  /** ISO timestamp of when the hospital last updated these numbers */
  updatedAt: string
  emergency: {
    status: ErStatus
    waitMinutes: number
    waitingCount: number
  }
  /** Whether the names are in `doctors` (signed-in staff only). */
  namesShown?: boolean
  doctors: Doctor[]
}

export const ER_STATUS_LABEL: Record<ErStatus, string> = {
  accepting: 'Accepting patients',
  busy: 'Very busy',
  diverting: 'Not accepting ambulances',
}

/** ER status and today's doctors, no sign-in needed. GET /api/public/status/. */
export function getPublicStatus(): Promise<PublicStatus> {
  return apiGet<PublicStatus>('/public/status/')
}
