import type { BedLevel, BloodLevel, ErStatus, PublicHospital } from '../../api/public'
import type { Tone } from '../../components/ui/StatusBadge'

/** The public pages refresh their figures this often while open. */
export const PUBLIC_REFRESH_MS = 60_000

export type Place = { latitude: number; longitude: number }

const EARTH_KM = 6371

/** Straight-line distance in km (haversine). Worked out in the browser: the visitor's location never leaves it. */
export function distanceKm(a: Place, b: Place): number {
  const rad = (deg: number) => (deg * Math.PI) / 180
  const dLat = rad(b.latitude - a.latitude)
  const dLng = rad(b.longitude - a.longitude)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_KM * Math.asin(Math.sqrt(h))
}

export function formatDistance(km: number): string {
  return km < 10 ? `${km.toFixed(1)} km` : `${Math.round(km)} km`
}

/** Where a department stands for someone choosing where to go: open ones by wait, then diverting, then unreported. */
function waitRank(h: PublicHospital): [number, number] {
  if (!h.emergency) return [2, 0]
  if (h.emergency.status === 'diverting') return [1, h.emergency.waitMinutes]
  return [0, h.emergency.waitMinutes]
}

/**
 * The directory's order: nearest first when the visitor shared their location, otherwise shortest emergency wait
 * first. Ties go by name, so the order never jumps between refreshes.
 */
export function sortHospitals(hospitals: readonly PublicHospital[], origin: Place | null): PublicHospital[] {
  const byName = (a: PublicHospital, b: PublicHospital) => a.name.localeCompare(b.name)
  if (origin) {
    return [...hospitals].sort((a, b) => distanceKm(origin, a) - distanceKm(origin, b) || byName(a, b))
  }
  return [...hospitals].sort((a, b) => {
    const [ga, wa] = waitRank(a)
    const [gb, wb] = waitRank(b)
    return ga - gb || wa - wb || byName(a, b)
  })
}

export const ER_TONE: Record<ErStatus, Tone> = { accepting: 'ok', busy: 'warning', diverting: 'critical' }
export const BED_TONE: Record<BedLevel, Tone> = { available: 'ok', limited: 'warning', full: 'critical' }
export const BLOOD_TONE: Record<BloodLevel, Tone> = { ok: 'ok', low: 'warning', critical: 'critical' }

/** "Gulshan-e-Iqbal" from "Block 7, Gulshan-e-Iqbal, Karachi": the area a card shows. */
export function areaOf(address: string): string {
  const parts = address.split(',').map((p) => p.trim()).filter(Boolean)
  if (parts.length >= 2 && /karachi/i.test(parts[parts.length - 1])) return parts[parts.length - 2]
  return parts[0] ?? address
}

export function mapLink(place: Place): string {
  return `https://www.google.com/maps/search/?api=1&query=${place.latitude},${place.longitude}`
}
