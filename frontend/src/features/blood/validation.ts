import { BLOOD_GROUPS, COMPONENTS, type BloodGroup, type BloodUnitInput, type Component } from '../../api/blood'
import type { FieldErrors } from '../auth/validation'

/** What the register-unit form holds. `collectedAt` is a date-input string (YYYY-MM-DD). */
export type UnitFormValues = {
  id: string
  group: BloodGroup
  component: Component
  collectedAt: string
  location: string
}

export type UnitField = keyof UnitFormValues

export const UNIT_FIELD_ORDER: readonly UnitField[] = ['id', 'group', 'component', 'collectedAt', 'location']

export const MAX_ID_LENGTH = 30

function componentLocations(component: Component): readonly string[] {
  return COMPONENTS.find((c) => c.id === component)!.location
}

export function emptyUnit(now: Date): UnitFormValues {
  return {
    id: '',
    group: BLOOD_GROUPS[0],
    component: COMPONENTS[0].id,
    collectedAt: now.toISOString().slice(0, 10),
    location: componentLocations(COMPONENTS[0].id)[0],
  }
}

/** Switching component keeps the storage location valid for it. */
export function withComponent(values: UnitFormValues, component: Component): UnitFormValues {
  return { ...values, component, location: componentLocations(component)[0] }
}

/** Same rules as the API (backend/apps/blood/serializers.py), checked before sending. */
export function validateUnit(values: UnitFormValues, now: Date): FieldErrors<UnitField> {
  const errors: FieldErrors<UnitField> = {}
  const id = values.id.trim()
  if (!id) errors.id = 'Enter the unit’s ID'
  else if (id.length > MAX_ID_LENGTH) errors.id = `Use at most ${MAX_ID_LENGTH} characters`
  if (!values.collectedAt) {
    errors.collectedAt = 'Enter the collection date'
  } else if (new Date(`${values.collectedAt}T00:00:00`).getTime() > now.getTime()) {
    errors.collectedAt = 'The collection date can’t be in the future'
  }
  if (!values.location) errors.location = 'Choose a storage location'
  return errors
}

export function toUnitInput(values: UnitFormValues): BloodUnitInput {
  return {
    id: values.id.trim(),
    group: values.group,
    component: values.component,
    collectedAt: new Date(`${values.collectedAt}T00:00:00`).toISOString(),
    location: values.location,
  }
}
