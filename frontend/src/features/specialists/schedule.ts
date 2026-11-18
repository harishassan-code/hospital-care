import { HOSPITAL_UTC_OFFSET } from '../../api/operatingRooms'
import type { SpecialistSummary } from '../../api/specialists'

/*
 * Clock times and dates for the hospital's zone, Asia/Karachi. Karachi has no daylight saving time, so the fixed
 * offset the API uses is exact. A viewer in any other zone still sees Karachi times.
 */

const ZONE = 'Asia/Karachi'

const CLOCK = new Intl.DateTimeFormat('en-GB', { timeZone: ZONE, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
const DAY = new Intl.DateTimeFormat('en-GB', { timeZone: ZONE, weekday: 'short', day: '2-digit', month: 'short' })
const DATE = new Intl.DateTimeFormat('en-GB', { timeZone: ZONE, day: '2-digit', month: 'short' })
const DAY_KEY = new Intl.DateTimeFormat('en-CA', { timeZone: ZONE, year: 'numeric', month: '2-digit', day: '2-digit' })

const asDate = (when: string | Date) => (typeof when === 'string' ? new Date(when) : when)

/** "08:00" */
export function karachiClock(iso: string): string {
  return CLOCK.format(asDate(iso))
}

/** "Wed 18 Nov" */
export function karachiDay(iso: string): string {
  return DAY.format(asDate(iso))
}

/** "18 Nov": the form the server uses in an overlap message. */
export function karachiDate(iso: string): string {
  return DATE.format(asDate(iso))
}

/** "Wed 18 Nov 20:00" */
export function karachiDateTime(iso: string): string {
  return `${karachiDay(iso)} ${karachiClock(iso)}`
}

/** "2026-11-18": the Karachi calendar day, for telling two moments on the same day apart. */
export function karachiDayKey(when: string | Date): string {
  return DAY_KEY.format(asDate(when))
}

/** The on-call line for a row: "On call until 08:00", with the day when it isn't the same day as `now`. */
export function onCallText(specialist: Pick<SpecialistSummary, 'onCallNow' | 'onCallUntil'>, now: Date): string {
  const until = specialist.onCallUntil
  if (!specialist.onCallNow || !until) return 'Not on call'
  if (karachiDayKey(until) === karachiDayKey(now)) return `On call until ${karachiClock(until)}`
  return `On call until ${karachiClock(until)} on ${karachiDay(until)}`
}

/** A Karachi date ("2026-11-18") and clock time ("08:00") as the ISO string the API takes. */
export function karachiIso(date: string, time: string): string {
  return `${date}T${time}:00${HOSPITAL_UTC_OFFSET}`
}
