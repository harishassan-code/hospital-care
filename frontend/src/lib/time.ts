/** Clock maths shared across features. Times of day are "HH:MM" strings on a 24-hour clock. */

export const DAY_MINUTES = 24 * 60

/** A start/end time of day; an end earlier than the start runs past midnight. */
export type TimeRange = { start: string; end: string }

export function toMinutes(hhmm: string): number {
  const [hours, minutes] = hhmm.split(':').map(Number)
  return hours * 60 + minutes
}

export function minutesOfDay(now: Date): number {
  return now.getHours() * 60 + now.getMinutes()
}

/** 24-hour "HH:MM", the way hospital boards show time. */
export function formatClock(date: Date): string {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

/** A range as [start, end) minute segments within one day. Overnight ranges become two segments. */
export function shiftSegments(start: string, end: string): Array<[number, number]> {
  const from = toMinutes(start)
  const to = toMinutes(end)
  if (to > from) return [[from, to]]
  return to === 0 ? [[from, DAY_MINUTES]] : [[from, DAY_MINUTES], [0, to]]
}

export function isInNow(range: TimeRange, now: Date): boolean {
  const minute = minutesOfDay(now)
  return shiftSegments(range.start, range.end).some(([from, to]) => minute >= from && minute < to)
}

/** The shift covering `now`, with whole minutes left until it ends. Shifts must cover the whole day. */
export function currentShift<S extends TimeRange>(shifts: readonly S[], now: Date): S & { minutesLeft: number } {
  const shift = shifts.find((s) => isInNow(s, now)) ?? shifts[0]
  const minutesLeft = (toMinutes(shift.end) - minutesOfDay(now) + DAY_MINUTES) % DAY_MINUTES || DAY_MINUTES
  return { ...shift, minutesLeft }
}

/** "52 min", "3 h 12 min", "4 d 6 h". */
export function formatDuration(minutes: number): string {
  const total = Math.max(0, Math.round(minutes))
  if (total < 60) return `${total} min`
  if (total < DAY_MINUTES) {
    const rest = total % 60
    return `${Math.floor(total / 60)} h${rest ? ` ${rest} min` : ''}`
  }
  const hours = Math.floor((total % DAY_MINUTES) / 60)
  return `${Math.floor(total / DAY_MINUTES)} d${hours ? ` ${hours} h` : ''}`
}

/** The local calendar date as "YYYY-MM-DD", for same-day comparisons. */
export function dateKey(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** The inverse of dateKey: a "YYYY-MM-DD" key as local midnight. */
export function fromDateKey(key: string): Date {
  const [year, month, day] = key.split('-').map(Number)
  return new Date(year, month - 1, day)
}

/** "15 Nov", or "15 Nov 2026" with the year. */
export function formatShortDate(date: Date, { year = false } = {}): string {
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', ...(year && { year: 'numeric' }) })
}

/** Hours from `now` until an ISO timestamp; negative once it has passed. */
export function hoursUntil(iso: string, now: Date): number {
  return (new Date(iso).getTime() - now.getTime()) / 3_600_000
}
