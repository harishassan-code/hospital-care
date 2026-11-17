import type { BedType } from './beds'
import type { BloodGroup, Component } from './blood'
import { apiGet, apiPost } from './client'
import type { EquipmentType } from './equipment'
import type { OrCapability } from './operatingRooms'

/** Most severe first. Lists come from the server in this order: severity, then the oldest case first (story #31). */
export type Severity = 'critical' | 'high' | 'moderate' | 'low'
export type CaseStatus = 'open' | 'matching' | 'partiallyFulfilled' | 'fulfilled' | 'escalated' | 'closed' | 'cancelled'

export type BloodNeed = { type: 'blood'; group: BloodGroup; component: Component; quantity: number }
export type BedNeed = { type: 'bed'; bedType: BedType; quantity: number }
export type EquipmentNeed = { type: 'equipment'; equipmentType: EquipmentType; quantity: number }
export type OperatingRoomNeed = { type: 'operatingRoom'; capability: OrCapability; quantity: number }
export type Need = BloodNeed | BedNeed | EquipmentNeed | OperatingRoomNeed

/** An emergency case (stories #30, #32). Shape of `CaseSerializer` in backend/apps/emergencies/serializers.py. */
export interface EmergencyCase {
  /** e.g. "EC-2026-0001" */
  id: string
  severity: Severity
  status: CaseStatus
  /** Optional bed or triage tag. Never a name. */
  patientRef: string
  hospital: { id: number; name: string } | null
  createdBy: string
  createdAt: string
  items: Need[]
}

export interface CaseInput {
  severity: Severity
  patientRef: string
  items: Need[]
}

/** One need in the network feed: what is asked for, and how much of it is already filled (story #36). */
export type FeedNeed = Need & { fulfilled: number }

/**
 * An active request in the network feed (story #36), from any hospital. Shape of `FeedEntry` in
 * backend/apps/emergencies/serializers.py. It carries no patient data, notes, timeline or author.
 */
export interface FeedEntry {
  reference: string
  hospital: { id: number; name: string } | null
  severity: Severity
  status: CaseStatus
  createdAt: string
  /** Only the needs of the type the feed was asked for. */
  needs: FeedNeed[]
}

export type FeedType = 'blood' | 'bed'
export type ResourceType = 'blood' | 'bed' | 'equipment' | 'operatingRoom'

/** A hospital that can supply one requirement (story #38). Shape of `CandidateSerializer`. */
export interface Candidate {
  hospital: { id: number; name: string }
  /** Matchable at that hospital for this requirement. */
  available: number
  /** Whether `available` is at least the shortfall. */
  covers: boolean
  /** Straight-line distance, one decimal. Null when either side has no coordinates or the case has no hospital. */
  distanceKm: number | null
  /** Estimated travel time in whole minutes (#39). Null with `distanceKm`. */
  travelMinutes: number | null
  /** Blood only: the soonest expiry among the matching units. */
  earliestExpiry?: string
  /** Blood only: 0 is the identical group; higher is a compatible substitute. */
  bestDonorRank?: number
  /** 1-based position in the item's list (story #41). */
  rank: number
  score: Score
  /** True only on rank 1, and only when its score is above 0. */
  recommended: boolean
}

/** One factor of a score (story #41): how well the candidate does on it, and what that is worth. */
export interface ScoreFactor {
  name: 'distance' | 'expiry' | 'quantity' | 'compatibility'
  /** "Distance", "Expiry", "Stock" or "Blood group match". */
  label: string
  /** 0 to 1, two decimals. */
  value: number
  /** This factor's share of the strategy's weights, 0 to 1, two decimals. */
  weight: number
  /** One decimal, out of 100. The factors' points add up to the score's total. */
  points: number
  /** The reason in plain words: "4.2 km, about 6 min", "expires in 3 days", "identical group". */
  detail: string
}

/** How a candidate scored under its item's strategy (story #41). `total` is 0 to 100, one decimal. */
export interface Score {
  total: number
  /** The strategy's name, as in `CandidateItem.strategy.name`. */
  strategy: string
  factors: ScoreFactor[]
}

/** One short requirement and the hospitals that can supply it. Shape of `CandidateItemSerializer`. */
export interface CandidateItem {
  itemId: number
  /** A label such as "O- red cells", "ICU bed", "Ventilator" or "Cardiac operating room". */
  need: string
  shortfall: number
  /** How the candidates are ordered, for people to read: "Earliest expiry first", "Nearest first". */
  strategy: { name: string; label: string }
  /** Best first, as the server ranks them. The client keeps this order. */
  candidates: Candidate[]
}

/** One short need a hospital cannot cover in full (story #42), with how many it is missing and how many it has. */
export interface UnmetNeed {
  itemId: number
  need: string
  /** How many more the hospital would need to cover the line. */
  missing: number
  /** What the hospital has for this line, after the lines before it on the same stock. 0 when it has none. */
  available: number
}

/**
 * A hospital judged across every short need at once (story #42). Shape of `HospitalMatchSerializer`. The list is
 * ordered: complete hospitals first, then by the needs covered, the score, and the distance.
 */
export interface HospitalMatch {
  /** 1-based position in the list. */
  rank: number
  hospital: { id: number; name: string }
  /** True when the hospital covers every short need. */
  complete: boolean
  /** True only on rank 1, and only when the hospital is complete. */
  recommended: boolean
  /** "2 of 3": the needs covered, of the short needs. */
  coverage: string
  coveredCount: number
  totalNeeds: number
  /** The mean of the hospital's #41 scores over the needs it has candidates for, one decimal, out of 100. */
  score: number
  /** Straight-line distance, one decimal. Null when either side has no coordinates or the case has no hospital. */
  distanceKm: number | null
  /** Estimated travel time in whole minutes (#39). Null with `distanceKm`. */
  travelMinutes: number | null
  /** The needs the hospital covers in full. */
  covered: { itemId: number; need: string }[]
  /** The needs it does not cover in full: partial ones, and those it has none of. */
  unmet: UnmetNeed[]
}

/**
 * The sources for a case (story #38). `items` holds only the short needs: empty when all are covered locally.
 * `hospitals` judges the hospitals across all of them at once (story #42): empty when nothing is short.
 */
export interface CandidatesResponse {
  reference: string
  items: CandidateItem[]
  hospitals: HospitalMatch[]
}

/** A move along the lifecycle (story #34). The names match REQUEST_LIFECYCLE in backend/apps/emergencies/models.py. */
export type CaseAction = 'startMatching' | 'partiallyFulfil' | 'fulfil' | 'escalate' | 'resumeMatching' | 'close' | 'cancel'

/** One entry in a case's timeline, oldest first. Shape of `StatusChangeSerializer`. */
export interface StatusChange {
  /** Empty for the first entry, when the case was opened. */
  fromStatus: CaseStatus | ''
  toStatus: CaseStatus
  action: CaseAction | 'create'
  note: string
  /** The user's name, or their email if they have no name. Null once the user has been removed. */
  actor: string | null
  at: string
}

/**
 * What the case's own hospital has for one need (story #33), the resources held for it (story #43) and what has been
 * allocated to it (story #45). Only the detail carries it. `reserved` counts the holds not yet allocated. `fulfilled`
 * is what has been allocated; `remaining` is the quantity less that.
 */
export type NeedAvailability = {
  itemId: number
  localAvailable: number
  shortfall: number
  reserved: number
  fulfilled: number
  remaining: number
}
export type AvailableNeed = Need & NeedAvailability

/** A hold on one resource for one need of a case (story #43). Shape of `ReservationSerializer`. */
export interface CaseReservation {
  id: number
  /** The need this hold is for: an `itemId` of the case's items. */
  itemId: number
  /** As staff name it: "O− red cells DN-0042", "Bed ICU-03", "Ventilator VENT-003" or "OR 1". */
  resource: string
  hospital: { id: number; name: string }
  /** Held until the hold expires or is released; allocated once the resource is handed over (story #45). */
  status: 'held' | 'allocated' | 'released' | 'expired'
  expiresAt: string
  /** The person who made the hold, or their email if they have no name. */
  reservedBy: string
  /** True when the signed-in user may allocate this hold now: it is held, and the user's role and hospital allow it. */
  canAllocate: boolean
}

/**
 * The record that a held resource was handed over to a case (story #45). Shape of `AllocationSerializer`. Permanent:
 * nothing changes or removes one.
 */
export interface CaseAllocation {
  id: number
  /** The need it was allocated for: an `itemId` of the case's items. */
  itemId: number
  resource: string
  hospital: { id: number; name: string }
  /** The person who allocated it, or their email if they have no name. */
  allocatedBy: string
  at: string
  note: string
}

/**
 * A held reservation at the user's hospital, for the Blood page's "Reserved for cases" panel (story #46). Shape of
 * `HeldReservationSerializer`. Ordered most urgent case first, then the hold expiring first.
 */
export interface HeldReservation {
  id: number
  type: ResourceType
  status: 'held'
  case: { reference: string; severity: Severity; status: CaseStatus }
  need: { itemId: number; label: string; quantity: number; fulfilled: number; remaining: number }
  resource: string
  expiresAt: string
  reservedBy: string
  canAllocate: boolean
}

/**
 * A case with its timeline, the moves valid from its current status, and what its hospital has for each need
 * (story #33). Shape of `CaseDetailSerializer`.
 */
export interface EmergencyCaseDetail extends EmergencyCase {
  items: AvailableNeed[]
  /** Units and beds still needed from other hospitals: the sum of the items' shortfalls. */
  shortfallTotal: number
  history: StatusChange[]
  actions: CaseAction[]
  /** The outcome note from the close (story #35): required to close, so set once the case is closed. Else null. */
  outcome: string | null
  /** The holds still in force on the case's stock: held and allocated (story #43). */
  reservations: CaseReservation[]
  /** The resources handed over to the case, oldest first (story #45). */
  allocations: CaseAllocation[]
}

export const SEVERITIES: readonly { id: Severity; label: string; hint: string }[] = [
  { id: 'critical', label: 'Critical', hint: 'Life-threatening: needed within the hour' },
  { id: 'high', label: 'High', hint: 'Serious: needed within a few hours' },
  { id: 'moderate', label: 'Moderate', hint: 'Needed today; can be planned' },
  { id: 'low', label: 'Low', hint: 'Can wait; handled after the rest' },
]

/** Same limits as the API. */
export const MAX_NEEDS = 10
export const MAX_QUANTITY: Record<Need['type'], number> = { blood: 20, bed: 5, equipment: 5, operatingRoom: 3 }
export const MAX_PATIENT_REF = 30
export const MAX_NOTE = 500

/** Cases at the user's hospital, most severe first, then oldest first. GET /api/emergencies/ (emergencies: view). */
export function getCases(): Promise<EmergencyCase[]> {
  return apiGet<EmergencyCase[]>('/emergencies/')
}

/** Open a case. POST /api/emergencies/ (emergencies: edit). */
export function createCase(input: CaseInput): Promise<EmergencyCase> {
  return apiPost<EmergencyCase>('/emergencies/', input)
}

/** The hospitals that can supply each short need of a case (story #38). GET /api/emergencies/<reference>/candidates/. */
export function getCandidates(reference: string): Promise<CandidatesResponse> {
  return apiGet<CandidatesResponse>(`/emergencies/${encodeURIComponent(reference)}/candidates/`)
}

/** One case with its timeline. GET /api/emergencies/<reference>/ (emergencies: view). Another hospital's is 404. */
export function getCase(reference: string): Promise<EmergencyCaseDetail> {
  return apiGet<EmergencyCaseDetail>(`/emergencies/${encodeURIComponent(reference)}/`)
}

/** Move a case. POST /api/emergencies/<reference>/actions/ (emergencies: edit). 409 if the move isn't allowed now. */
export function postCaseAction(reference: string, action: CaseAction, note: string): Promise<EmergencyCaseDetail> {
  return apiPost<EmergencyCaseDetail>(`/emergencies/${encodeURIComponent(reference)}/actions/`, { action, note })
}

/**
 * Active requests from every hospital, most urgent first, with their needs of one type. GET /api/emergencies/feed/
 * (emergencies: view, every staff role).
 */
export function getFeed(type: FeedType): Promise<FeedEntry[]> {
  return apiGet<FeedEntry[]>(`/emergencies/feed/?type=${type}`)
}

/**
 * Hold up to `quantity` of one need's resources at the case's own hospital (story #43). Returns the holds made, which
 * can be fewer than asked. POST /api/emergencies/<reference>/reservations/ (emergencies: edit). 400 with a `detail`
 * when nothing is free or the need has no room left.
 */
export function reserveStock(reference: string, itemId: number, quantity: number): Promise<CaseReservation[]> {
  return apiPost<CaseReservation[]>(`/emergencies/${encodeURIComponent(reference)}/reservations/`, { itemId, quantity })
}

/** Release a held reservation. POST /api/emergencies/<reference>/reservations/<id>/release/ (emergencies: edit). 409 if it isn't held. */
export function releaseReservation(reference: string, id: number): Promise<CaseReservation> {
  return apiPost<CaseReservation>(`/emergencies/${encodeURIComponent(reference)}/reservations/${id}/release/`, {})
}

/**
 * Held reservations at the user's hospital (every hospital for admins), for the types the role can see, most urgent
 * first. GET /api/reservations/?status=held&type=blood. 403 when the role can't see the type.
 */
export function getHeldReservations(type?: ResourceType): Promise<HeldReservation[]> {
  return apiGet<HeldReservation[]>(`/reservations/?status=held${type ? `&type=${type}` : ''}`)
}

/** Allocate one held reservation to its case (story #46). POST /api/reservations/<id>/allocate/. 409 if it can't be. */
export function allocateReservation(id: number, note = ''): Promise<CaseAllocation> {
  return apiPost<CaseAllocation>(`/reservations/${id}/allocate/`, { note })
}

/**
 * Allocate several held reservations together: all of them, or none (story #46). POST /api/reservations/allocate/.
 * 409 when one of them can't be allocated, and nothing changes.
 */
export function allocateReservations(ids: number[]): Promise<CaseAllocation[]> {
  return apiPost<CaseAllocation[]>('/reservations/allocate/', { ids })
}
