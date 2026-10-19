import type { Hospital, HospitalInput, HospitalType } from '../../api/hospitals'
import type { FieldErrors } from '../auth/validation'

/** What the form holds: numbers stay as typed text until they're checked. */
export type HospitalFormValues = {
  name: string
  type: HospitalType
  address: string
  latitude: string
  longitude: string
  phone: string
  isActive: boolean
  capabilities: string[]
}

export type HospitalField = keyof HospitalFormValues

/** On-screen order, so focus goes to the first invalid field. Each input's id equals its key. */
export const HOSPITAL_FIELD_ORDER: readonly HospitalField[] = ['name', 'type', 'address', 'latitude', 'longitude', 'phone']

export const EMPTY_HOSPITAL: HospitalFormValues = {
  name: '',
  type: 'hospital',
  address: '',
  latitude: '',
  longitude: '',
  phone: '',
  isActive: true,
  capabilities: [],
}

const PHONE = /^\+?[\d\s-]{7,20}$/
const DECIMAL = /^-?\d+(\.\d{1,6})?$/

function coordinateError(text: string, label: 'latitude' | 'longitude', limit: number): string | undefined {
  const value = text.trim()
  if (!value) return `Enter the ${label}`
  if (!DECIMAL.test(value)) return `Enter the ${label} as a decimal number with up to 6 decimal places, e.g. 24.8607`
  if (Math.abs(Number(value)) > limit) return `The ${label} must be between -${limit} and ${limit}`
}

/** Same rules as the API (docs/architecture/api-contracts.md), checked before sending. */
export function validateHospital(values: HospitalFormValues): FieldErrors<HospitalField> {
  const errors: FieldErrors<HospitalField> = {}
  const name = values.name.trim()
  if (!name) errors.name = 'Enter the hospital’s name'
  else if (name.length > 150) errors.name = 'Use at most 150 characters'
  const address = values.address.trim()
  if (!address) errors.address = 'Enter the street address'
  else if (address.length > 300) errors.address = 'Use at most 300 characters'
  const latitude = coordinateError(values.latitude, 'latitude', 90)
  if (latitude) errors.latitude = latitude
  const longitude = coordinateError(values.longitude, 'longitude', 180)
  if (longitude) errors.longitude = longitude
  const phone = values.phone.trim()
  if (phone && !PHONE.test(phone)) errors.phone = 'Enter a phone number using digits, spaces, + or -'
  return errors
}

export function toHospitalInput(values: HospitalFormValues): HospitalInput {
  return {
    name: values.name.trim(),
    type: values.type,
    address: values.address.trim(),
    latitude: Number(values.latitude.trim()),
    longitude: Number(values.longitude.trim()),
    phone: values.phone.trim(),
    isActive: values.isActive,
    capabilities: values.capabilities,
  }
}

export function toFormValues(hospital: Hospital): HospitalFormValues {
  return {
    name: hospital.name,
    type: hospital.type,
    address: hospital.address,
    latitude: String(hospital.latitude),
    longitude: String(hospital.longitude),
    phone: hospital.phone,
    isActive: hospital.isActive,
    capabilities: hospital.capabilities,
  }
}
