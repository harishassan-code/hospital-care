import { apiGet, apiPost } from './client'

export type EquipmentType = 'ventilator' | 'monitor' | 'defibrillator' | 'dialysis'
export type EquipmentStatus = 'available' | 'inUse' | 'maintenance' | 'outOfService'

export const EQUIPMENT_TYPES: readonly { value: EquipmentType; label: string }[] = [
  { value: 'ventilator', label: 'Ventilators' },
  { value: 'monitor', label: 'Patient monitors' },
  { value: 'defibrillator', label: 'Defibrillators' },
  { value: 'dialysis', label: 'Dialysis machines' },
]

export const EQUIPMENT_STATUSES: readonly { value: EquipmentStatus; label: string }[] = [
  { value: 'available', label: 'Available' },
  { value: 'inUse', label: 'In use' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'outOfService', label: 'Out of service' },
]

/** One piece of critical equipment (story #26). */
export interface Equipment {
  id: number
  identifier: string
  type: EquipmentType
  name: string
  location: string
  status: EquipmentStatus
  statusSince: string
  hospital: string | null
}

export type EquipmentInput = Pick<Equipment, 'identifier' | 'type' | 'name' | 'location' | 'status'>

/** The equipment in the user's hospital. GET /api/equipment/ (equipment: view). */
export function getEquipment(): Promise<Equipment[]> {
  return apiGet<Equipment[]>('/equipment/')
}

/** Register equipment. POST /api/equipment/ (equipment: edit). 400 with field errors, e.g. a taken asset tag. */
export function createEquipment(input: EquipmentInput): Promise<Equipment> {
  return apiPost<Equipment>('/equipment/', input)
}
