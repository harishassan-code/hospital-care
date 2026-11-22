import { BLOOD_GROUPS, type BloodGroup } from '../../api/blood'
import type { DonorInput } from '../../api/donors'
import type { FieldErrors } from '../auth/validation'

/** Limits and patterns the API checks (backend/apps/blood/serializers.py and models.py). Checked here before sending. */
export const MAX_NAME = 150
export const MAX_EMAIL = 254
export const MAX_REASON = 300
const PHONE = /^\+?[\d\s-]{7,20}$/
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export type DonorFormValues = {
  fullName: string
  bloodGroup: '' | BloodGroup
  phone: string
  email: string
}

export type DonorField = keyof DonorFormValues

export const DONOR_FIELD_ORDER: readonly DonorField[] = ['fullName', 'bloodGroup', 'phone', 'email']

export function emptyDonor(): DonorFormValues {
  return { fullName: '', bloodGroup: '', phone: '', email: '' }
}

export function validateDonor(values: DonorFormValues): FieldErrors<DonorField> {
  const errors: FieldErrors<DonorField> = {}
  const name = values.fullName.trim()
  if (!name) errors.fullName = 'Enter the donor’s full name'
  else if (name.length > MAX_NAME) errors.fullName = `Use at most ${MAX_NAME} characters`
  if (!values.bloodGroup || !BLOOD_GROUPS.includes(values.bloodGroup)) errors.bloodGroup = 'Choose a blood group'
  const phone = values.phone.trim()
  if (phone && !PHONE.test(phone)) errors.phone = 'Use 7 to 20 digits, spaces or dashes, with an optional leading +'
  const email = values.email.trim()
  if (email && (email.length > MAX_EMAIL || !EMAIL.test(email))) {
    errors.email = 'Enter an email with an @ and a domain, like name@example.com'
  }
  return errors
}

/** The request body: trimmed, with optional fields left out when empty. */
export function toDonorInput(values: DonorFormValues): DonorInput {
  const input: DonorInput = { fullName: values.fullName.trim(), bloodGroup: values.bloodGroup as BloodGroup }
  const phone = values.phone.trim()
  const email = values.email.trim()
  if (phone) input.phone = phone
  if (email) input.email = email
  return input
}

export type ScreeningFormValues = {
  /** '' until a choice is made. */
  eligible: '' | 'yes' | 'no'
  reason: string
  /** "YYYY-MM-DD", or '' when empty. Ignored when noEndDate is ticked. */
  endDate: string
  noEndDate: boolean
}

export type ScreeningField = 'eligible' | 'reason' | 'endDate'

export const SCREENING_FIELD_ORDER: readonly ScreeningField[] = ['eligible', 'reason', 'endDate']

export function emptyScreening(): ScreeningFormValues {
  return { eligible: '', reason: '', endDate: '', noEndDate: false }
}

/** `today` is "YYYY-MM-DD". An end date must be after it. */
export function validateScreening(values: ScreeningFormValues, today: string): FieldErrors<ScreeningField> {
  const errors: FieldErrors<ScreeningField> = {}
  if (!values.eligible) errors.eligible = 'Choose eligible or not eligible'
  if (values.eligible !== 'no') return errors
  const reason = values.reason.trim()
  if (!reason) errors.reason = 'Enter the reason. Keep it short and leave out names'
  else if (reason.length > MAX_REASON) errors.reason = `Use at most ${MAX_REASON} characters`
  if (!values.noEndDate) {
    if (!values.endDate) errors.endDate = 'Choose an end date, or tick No end date'
    else if (values.endDate <= today) errors.endDate = 'The end date must be after today'
  }
  return errors
}
