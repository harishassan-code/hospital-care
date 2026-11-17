import type { BedType } from '../../api/beds'
import { BLOOD_GROUPS, COMPONENTS, type BloodGroup, type Component } from '../../api/blood'
import { ApiError } from '../../api/client'
import type { EquipmentType } from '../../api/equipment'
import { OR_CAPABILITIES, type OrCapability } from '../../api/operatingRooms'
import {
  MAX_NEEDS,
  MAX_PATIENT_REF,
  MAX_QUANTITY,
  type CaseAction,
  type CaseAllocation,
  type CaseInput,
  type HeldReservation,
  type CaseStatus,
  type Need,
  type Severity,
  type StatusChange,
} from '../../api/emergencies'
import type { Tone } from '../../components/ui/StatusBadge'
import { TYPE_LABEL } from '../beds/beds'
import { COMPONENT_LABEL, formatGroup } from '../blood/blood'

/** Singular names for the equipment a case can ask for: "2 × Ventilator". */
export const EQUIPMENT_NEED_LABEL: Record<EquipmentType, string> = {
  ventilator: 'Ventilator',
  monitor: 'Patient monitor',
  defibrillator: 'Defibrillator',
  dialysis: 'Dialysis machine',
}

/** "4 × O− red cells", "1 × ICU bed", "2 × Ventilator" or "1 × Operating room (cardiac)". */
export function describeNeed(need: Need): string {
  if (need.type === 'blood') return `${need.quantity} × ${formatGroup(need.group)} ${COMPONENT_LABEL[need.component].toLowerCase()}`
  if (need.type === 'bed') return `${need.quantity} × ${TYPE_LABEL[need.bedType]} bed${need.quantity === 1 ? '' : 's'}`
  if (need.type === 'equipment') return `${need.quantity} × ${EQUIPMENT_NEED_LABEL[need.equipmentType]}`
  const capability = OR_CAPABILITIES.find((c) => c.value === need.capability)?.label ?? need.capability
  return `${need.quantity} × Operating room (${capability.toLowerCase()})`
}

/** The case's summary of local availability (story #33). `total` is the server's `shortfallTotal`. */
export function shortfallSummary(total: number): string {
  if (total === 0) return 'Everything is available here'
  return total === 1 ? '1 unit or bed needed from other hospitals' : `${total} units/beds needed from other hospitals`
}

export const STATUS_LABEL: Record<CaseStatus, string> = {
  open: 'Open',
  matching: 'Matching',
  partiallyFulfilled: 'Partially fulfilled',
  fulfilled: 'Fulfilled',
  escalated: 'Escalated',
  closed: 'Closed',
  cancelled: 'Cancelled',
}

/** The button label for each move. */
export const ACTION_LABEL: Record<CaseAction, string> = {
  startMatching: 'Start matching',
  partiallyFulfil: 'Mark partially fulfilled',
  fulfil: 'Mark fulfilled',
  escalate: 'Escalate',
  resumeMatching: 'Resume matching',
  close: 'Close case',
  cancel: 'Cancel case',
}

export const SEVERITY_TONE: Record<Severity, Tone> = { critical: 'critical', high: 'warning', moderate: 'neutral', low: 'neutral' }

type Transition = { action: CaseAction; next: CaseStatus }

/**
 * The lifecycle, mirrored from REQUEST_LIFECYCLE in backend/apps/emergencies/models.py. The server decides which moves
 * are allowed; this copy lets the mock API and the page use the same moves. Closed and cancelled have none.
 */
const TRANSITIONS: Record<CaseStatus, readonly Transition[]> = {
  open: [
    { action: 'startMatching', next: 'matching' },
    { action: 'escalate', next: 'escalated' },
    { action: 'cancel', next: 'cancelled' },
  ],
  matching: [
    { action: 'partiallyFulfil', next: 'partiallyFulfilled' },
    { action: 'fulfil', next: 'fulfilled' },
    { action: 'escalate', next: 'escalated' },
    { action: 'cancel', next: 'cancelled' },
  ],
  partiallyFulfilled: [
    { action: 'fulfil', next: 'fulfilled' },
    { action: 'escalate', next: 'escalated' },
    { action: 'close', next: 'closed' },
  ],
  fulfilled: [{ action: 'close', next: 'closed' }],
  escalated: [
    { action: 'resumeMatching', next: 'matching' },
    { action: 'close', next: 'closed' },
  ],
  closed: [],
  cancelled: [],
}

/** The moves valid from `status`, in the order the lifecycle lists them. */
export function actionsFor(status: CaseStatus): CaseAction[] {
  return TRANSITIONS[status].map((t) => t.action)
}

/** The status after `action`, or undefined when the lifecycle refuses the move. */
export function nextStatus(status: CaseStatus, action: CaseAction): CaseStatus | undefined {
  return TRANSITIONS[status].find((t) => t.action === action)?.next
}

/** "Matching → Partially fulfilled", or "Case opened" for the first entry of a timeline. */
export function describeMove(change: StatusChange): string {
  return change.fromStatus ? `${STATUS_LABEL[change.fromStatus]} → ${STATUS_LABEL[change.toStatus]}` : 'Case opened'
}

/** The server's blood group code, with the minus sign the pages use: "O- red cells" → "O− red cells". */
export const withMinus = (label: string) => label.replace(/^(AB|A|B|O)-/, '$1−')

/** One need of a case with the held reservations for it (story #46). */
export type HeldNeedGroup = { need: HeldReservation['need']; holds: HeldReservation[] }
/** One case with the needs that have holds, in the order the server sends (most urgent case first). */
export type HeldCaseGroup = { case: HeldReservation['case']; needs: HeldNeedGroup[] }

/** Groups held reservations by case, then by need, keeping the server's order. */
export function groupHeld(holds: HeldReservation[]): HeldCaseGroup[] {
  const cases = new Map<string, HeldCaseGroup>()
  for (const hold of holds) {
    const group = cases.get(hold.case.reference) ?? { case: hold.case, needs: [] }
    cases.set(hold.case.reference, group)
    let need = group.needs.find((n) => n.need.itemId === hold.need.itemId)
    if (!need) group.needs.push((need = { need: hold.need, holds: [] }))
    need.holds.push(hold)
  }
  return [...cases.values()]
}

/** One row of a case's timeline: a status move, or a resource handed over to the case (story #45). */
export type TimelineEntry = { kind: 'move'; at: string; change: StatusChange } | { kind: 'allocation'; at: string; allocation: CaseAllocation }

/**
 * The status moves and the allocations of a case as one timeline, oldest first. The sort is stable and the allocations
 * come first, so an allocation shows before the status move it caused at the same moment. Compares real times, since
 * the server's timestamps vary in offset.
 */
export function timelineOf(history: StatusChange[], allocations: CaseAllocation[]): TimelineEntry[] {
  const entries: TimelineEntry[] = [
    ...allocations.map((allocation): TimelineEntry => ({ kind: 'allocation', at: allocation.at, allocation })),
    ...history.map((change): TimelineEntry => ({ kind: 'move', at: change.at, change })),
  ]
  return entries.sort((a, b) => Date.parse(a.at) - Date.parse(b.at))
}

/** One row of the "What's needed" step. `quantity` is the raw input text; `key` stays stable as rows come and go. */
export type NeedDraft = {
  key: number
  type: Need['type']
  group: BloodGroup
  component: Component
  bedType: BedType
  equipmentType: EquipmentType
  capability: OrCapability
  quantity: string
}

export type CaseFormValues = { severity: Severity | ''; patientRef: string; needs: NeedDraft[] }

/**
 * Field errors: `severity`, `patientRef`, `needs` (the list as a whole) and `<field>-<key>` per row, where the field
 * is the row's control: `quantity`, `group`, `component`, `bedType`, `equipmentType` or `capability`.
 */
export type CaseErrors = Record<string, string | undefined>

/** The three steps of the form (#30: at most 3). */
export const STEPS = ['Case', 'What’s needed', 'Review'] as const

export function newNeed(key: number): NeedDraft {
  return {
    key,
    type: 'blood',
    group: BLOOD_GROUPS[0],
    component: COMPONENTS[0].id,
    bedType: 'icu',
    equipmentType: 'ventilator',
    capability: 'general',
    quantity: '1',
  }
}

export function emptyCase(): CaseFormValues {
  return { severity: '', patientRef: '', needs: [newNeed(1)] }
}

/** Step 1: severity is required; the patient reference is optional and short. */
export function validateCaseStep(values: CaseFormValues): CaseErrors {
  const errors: CaseErrors = {}
  if (!values.severity) errors.severity = 'Choose how severe the case is'
  if (values.patientRef.trim().length > MAX_PATIENT_REF) errors.patientRef = `Use at most ${MAX_PATIENT_REF} characters`
  return errors
}

/** Step 2: one to MAX_NEEDS needs, each with a whole-number quantity within its type's limit. */
export function validateNeedsStep(values: CaseFormValues): CaseErrors {
  const errors: CaseErrors = {}
  if (values.needs.length === 0) errors.needs = 'Add at least one thing the case needs'
  else if (values.needs.length > MAX_NEEDS) errors.needs = `List at most ${MAX_NEEDS} needs`
  for (const need of values.needs) {
    const text = need.quantity.trim()
    const quantity = Number(text)
    const max = MAX_QUANTITY[need.type]
    if (!/^\d+$/.test(text) || quantity < 1) errors[`quantity-${need.key}`] = 'Enter a whole number of 1 or more'
    else if (quantity > max) errors[`quantity-${need.key}`] = `At most ${max} per line; add another line for more`
  }
  return errors
}

export function hasErrors(errors: CaseErrors): boolean {
  return Object.values(errors).some(Boolean)
}

export function toNeed(draft: NeedDraft): Need {
  const quantity = Number(draft.quantity.trim())
  if (draft.type === 'blood') return { type: 'blood', group: draft.group, component: draft.component, quantity }
  if (draft.type === 'bed') return { type: 'bed', bedType: draft.bedType, quantity }
  if (draft.type === 'equipment') return { type: 'equipment', equipmentType: draft.equipmentType, quantity }
  return { type: 'operatingRoom', capability: draft.capability, quantity }
}

export function toCaseInput(values: CaseFormValues): CaseInput {
  return { severity: values.severity as Severity, patientRef: values.patientRef.trim(), items: values.needs.map(toNeed) }
}

const first = (value: unknown): string | undefined => (Array.isArray(value) ? value.find((v) => typeof v === 'string') : undefined)

/**
 * A 400 from POST /emergencies/ as form errors. Errors on one need come back keyed by its position,
 * `{items: {"0": {quantity: ["…"]}}}`, and each field's error lands on that row's control; errors on the list as a
 * whole come back as `{items: ["…"]}`.
 */
export function serverErrors(error: unknown, needs: NeedDraft[]): CaseErrors {
  const body = error instanceof ApiError && typeof error.body === 'object' && error.body !== null ? (error.body as Record<string, unknown>) : {}
  const errors: CaseErrors = { severity: first(body.severity), patientRef: first(body.patientRef) }
  const items = body.items
  if (Array.isArray(items)) {
    errors.needs = first(items)
  } else if (typeof items === 'object' && items !== null) {
    for (const [index, fields] of Object.entries(items as Record<string, Record<string, unknown>>)) {
      const need = needs[Number(index)]
      if (!need) continue
      for (const [field, messages] of Object.entries(fields ?? {})) {
        const message = first(messages)
        if (message) errors[`${field}-${need.key}`] = message
      }
    }
  }
  return errors
}

/** Which step to send the user back to for these errors (0 or 1), or null if there are none. */
export function stepWithErrors(errors: CaseErrors): number | null {
  if (errors.severity || errors.patientRef) return 0
  return hasErrors(errors) ? 1 : null
}

// ── The quick blood request (story #36) ──────────────────────────────────────────────────────────

/** The quick form's values: one blood need and its urgency. `quantity` is the raw input text. */
export type BloodRequestValues = {
  severity: Severity | ''
  group: BloodGroup
  component: Component
  quantity: string
}

/** Field errors by field name; `form` holds a message about the request as a whole. */
export type BloodRequestErrors = Partial<Record<'severity' | 'group' | 'component' | 'quantity' | 'form', string>>

export function emptyBloodRequest(): BloodRequestValues {
  return { severity: '', group: BLOOD_GROUPS[0], component: COMPONENTS[0].id, quantity: '1' }
}

/** Urgency is required. The quantity is a whole number from 1 to the blood limit, the same as the API's. */
export function validateBloodRequest(values: BloodRequestValues): BloodRequestErrors {
  const errors: BloodRequestErrors = {}
  if (!values.severity) errors.severity = 'Choose how urgent the request is'
  const text = values.quantity.trim()
  const max = MAX_QUANTITY.blood
  if (!/^\d+$/.test(text) || Number(text) < 1) errors.quantity = 'Enter a whole number of 1 or more'
  else if (Number(text) > max) errors.quantity = `At most ${max} units per request; send another request for more`
  return errors
}

/** A blood request is a case with one blood need (story #36). It has no patient reference. */
export function toBloodRequest(values: BloodRequestValues): CaseInput {
  return {
    severity: values.severity as Severity,
    patientRef: '',
    items: [{ type: 'blood', group: values.group, component: values.component, quantity: Number(values.quantity.trim()) }],
  }
}

/** A 400 from POST /emergencies/ as the quick form's field errors. The one need is item "0". */
export function bloodRequestErrors(error: unknown): BloodRequestErrors {
  const body = error instanceof ApiError && typeof error.body === 'object' && error.body !== null ? (error.body as Record<string, unknown>) : {}
  const items = body.items
  const need = typeof items === 'object' && items !== null && !Array.isArray(items) ? (items as Record<string, Record<string, unknown>>)['0'] : undefined
  return {
    severity: first(body.severity),
    group: first(need?.group),
    component: first(need?.component),
    quantity: first(need?.quantity),
    form: first(items),
  }
}
