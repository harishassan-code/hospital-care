import { apiGet } from './client'

export interface Batch {
  number: string
  /** Local calendar date "YYYY-MM-DD". */
  expiresOn: string
  quantity: number
}

export interface Medicine {
  id: string
  /** Generic name. */
  name: string
  strength: string
  form: string
  category: string
  /** Counting unit, e.g. "tablets", "vials". */
  unit: string
  reorderLevel: number
  /** Average units used per day over the last 30 days. */
  dailyUse: number
  location: string
  /** On the ISMP list of high-alert medications: errors cause the most harm. */
  highAlert: boolean
  /** Controlled drug: kept in the CD cabinet, every movement double-signed. */
  controlled: boolean
  batches: Batch[]
}

/** Every medicine with its batches. GET /api/pharmacy/stock/ (pharmacy: view). */
export function getMedicines(): Promise<Medicine[]> {
  return apiGet<Medicine[]>('/pharmacy/stock/')
}
