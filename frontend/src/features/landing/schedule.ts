import type { Doctor } from '../../api/publicStatus'
import { isInNow, toMinutes } from '../../lib/time'

export function departmentsOf(doctors: Doctor[]): string[] {
  return [...new Set(doctors.map((d) => d.department))].sort()
}

export function sortForDisplay(doctors: Doctor[], now: Date): Doctor[] {
  return [...doctors].sort(
    (a, b) => Number(isInNow(b, now)) - Number(isInNow(a, now)) || toMinutes(a.start) - toMinutes(b.start),
  )
}
