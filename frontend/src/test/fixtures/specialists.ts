import type { OnCallWindow } from '../../api/specialists'

/** The Karachi day the sample specialists are on duty. Tests set the clock to noon on this day. */
export const SAMPLE_DAY = '2026-11-18'
/** Noon in Karachi on SAMPLE_DAY, as the clock tests use it. */
export const SAMPLE_NOON = `${SAMPLE_DAY}T12:00:00+05:00`

/** A specialist as the fake server keeps them: the profile, and every window in start order. */
export interface SpecialistRecord {
  id: number
  name: string
  specialty: string
  isActive: boolean
  hospital: { id: number; name: string }
  windows: OnCallWindow[]
}

const CITYCARE = { id: 1, name: 'CityCare General Hospital' }
const SEAVIEW = { id: 2, name: 'Seaview Hospital' }

/**
 * Four specialists across two hospitals: one on call now, one on call later (an overnight shift that starts at 20:00),
 * one on call now at Seaview, and one deactivated who is inside a window but is never on call. Times are Karachi.
 */
export function sampleSpecialists(): SpecialistRecord[] {
  const day = SAMPLE_DAY
  const nextDay = '2026-11-19'
  return [
    {
      id: 1,
      name: 'Dr. Ayesha Khan',
      specialty: 'Cardiology',
      isActive: true,
      hospital: CITYCARE,
      windows: [{ id: 101, startsAt: `${day}T08:00:00+05:00`, endsAt: `${day}T20:00:00+05:00` }],
    },
    {
      id: 2,
      name: 'Dr. Usman Farooq',
      specialty: 'Emergency medicine',
      isActive: true,
      hospital: CITYCARE,
      windows: [{ id: 201, startsAt: `${day}T20:00:00+05:00`, endsAt: `${nextDay}T08:00:00+05:00` }],
    },
    {
      id: 3,
      name: 'Dr. Omar Sheikh',
      specialty: 'Cardiology',
      isActive: true,
      hospital: SEAVIEW,
      windows: [{ id: 301, startsAt: `${day}T10:00:00+05:00`, endsAt: `${day}T13:00:00+05:00` }],
    },
    {
      id: 4,
      name: 'Dr. Sana Malik',
      specialty: 'Paediatrics',
      isActive: false,
      hospital: SEAVIEW,
      windows: [{ id: 401, startsAt: `${day}T08:00:00+05:00`, endsAt: `${day}T20:00:00+05:00` }],
    },
  ]
}
