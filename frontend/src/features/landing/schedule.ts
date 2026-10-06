import type { Doctor } from '../../api/publicStatus'

export const DAY_MINUTES = 24 * 60

export function toMinutes(hhmm: string): number {
  const [hours, minutes] = hhmm.split(':').map(Number)
  return hours * 60 + minutes
}

/** 24-hour "HH:MM", the way hospital boards show time. */
export function formatClock(date: Date): string {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

export function minutesOfDay(now: Date): number {
  return now.getHours() * 60 + now.getMinutes()
}

/** A shift as [start, end) minute ranges within one day. Overnight shifts become two ranges. */
export function shiftSegments(start: string, end: string): Array<[number, number]> {
  const from = toMinutes(start)
  const to = toMinutes(end)
  if (to > from) return [[from, to]]
  return to === 0 ? [[from, DAY_MINUTES]] : [[from, DAY_MINUTES], [0, to]]
}

export function isInNow(doctor: Pick<Doctor, 'start' | 'end'>, now: Date): boolean {
  const minute = minutesOfDay(now)
  return shiftSegments(doctor.start, doctor.end).some(([from, to]) => minute >= from && minute < to)
}

export function departmentsOf(doctors: Doctor[]): string[] {
  return [...new Set(doctors.map((d) => d.department))].sort()
}

export function sortForDisplay(doctors: Doctor[], now: Date): Doctor[] {
  return [...doctors].sort(
    (a, b) => Number(isInNow(b, now)) - Number(isInNow(a, now)) || toMinutes(a.start) - toMinutes(b.start),
  )
}
