import { ApiError } from '../../api/client'
import { DONOR_FIRST_SLOT, DONOR_LAST_SLOT, DONOR_SLOT_MINUTES, type Appointment, type Donor } from '../../api/donors'
import { dateKey, formatClock, formatShortDate, fromDateKey, toMinutes } from '../../lib/time'

/** Start times from DONOR_FIRST_SLOT to DONOR_LAST_SLOT, both included, as "HH:MM". */
export function slotTimes(): string[] {
  const times: string[] = []
  for (let minute = toMinutes(DONOR_FIRST_SLOT); minute <= toMinutes(DONOR_LAST_SLOT); minute += DONOR_SLOT_MINUTES) {
    const hours = String(Math.floor(minute / 60)).padStart(2, '0')
    const mins = String(minute % 60).padStart(2, '0')
    times.push(`${hours}:${mins}`)
  }
  return times
}

/** A slot as a moment: a day ("YYYY-MM-DD") and a time ("HH:MM") in the browser's zone (the hospital's zone). */
export function slotStart(day: string, time: string): Date {
  const [hours, minutes] = time.split(':').map(Number)
  const start = fromDateKey(day)
  start.setHours(hours, minutes, 0, 0)
  return start
}

export type SlotState = 'free' | 'booked' | 'passed'

/** Free, booked (by someone else at this hospital) or passed. A passed time can't be booked, whatever is there. */
export function slotState(start: Date, taken: ReadonlySet<number>, now: Date): SlotState {
  if (start.getTime() <= now.getTime()) return 'passed'
  return taken.has(start.getTime()) ? 'booked' : 'free'
}

/**
 * The start times already booked at the hospital a new booking would go to. The server's rule: the actor's hospital,
 * else the donor's (`book_appointment`). Null counts as its own hospital, so admins with no hospital match each other.
 */
export function bookedStarts(appointments: readonly Appointment[], bookingHospitalId: number | null): Set<number> {
  return new Set(
    appointments
      .filter((a) => a.status === 'booked' && a.hospitalId === bookingHospitalId)
      .map((a) => new Date(a.startsAt).getTime()),
  )
}

export function bookingHospitalId(actorHospitalId: number | null, donor: Donor): number | null {
  return actorHospitalId ?? donor.hospitalId
}

/** "12 Dec 2026" for a "YYYY-MM-DD" day. */
export function formatDay(day: string): string {
  return formatShortDate(fromDateKey(day), { year: true })
}

/** "12 Dec 2026, 10:00" for an ISO timestamp. */
export function formatSlot(startsAt: string): string {
  const when = new Date(startsAt)
  return `${formatDay(dateKey(when))}, ${formatClock(when)}`
}

/** "Eligible", "Not eligible until 12 Dec 2026" or "Not eligible, no end date". Words, not colour alone. */
export function eligibilityLabel(donor: Pick<Donor, 'eligible' | 'eligibleFrom'>): string {
  if (donor.eligible) return 'Eligible'
  if (donor.eligibleFrom) return `Not eligible until ${formatDay(donor.eligibleFrom)}`
  return 'Not eligible, no end date'
}

export function lastDonationLabel(lastDonationAt: string | null): string {
  return lastDonationAt ? formatShortDate(new Date(lastDonationAt), { year: true }) : 'None yet'
}

/**
 * The first day a donor can be booked: today, or their eligibleFrom if that is later. Null when a deferral has
 * no end date, so nothing can be booked.
 */
export function firstBookableDay(donor: Pick<Donor, 'eligible' | 'eligibleFrom'>, today: string): string | null {
  if (donor.eligible) return today
  if (!donor.eligibleFrom) return null
  return donor.eligibleFrom > today ? donor.eligibleFrom : today
}

/** The server's `detail` message from an error answer (403 and 409 send one), when it sent one. */
export function serverDetail(error: unknown): string | undefined {
  const body = error instanceof ApiError ? error.body : null
  const detail = typeof body === 'object' && body !== null ? (body as { detail?: unknown }).detail : undefined
  return typeof detail === 'string' ? detail : undefined
}

/** The HTTP status of a failed call, or 0 when the server couldn't be reached. */
export function statusOf(error: unknown): number {
  return error instanceof ApiError ? error.status : 0
}
