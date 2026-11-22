import type { Appointment, Donor } from '../../api/donors'
import type { BloodUnit } from '../../api/blood'
import { dateKey } from '../../lib/time'

/**
 * Synthetic donors for tests and the demo. Names are invented, emails use example.com, and phone numbers are
 * placeholders. Nothing here is a real person.
 */

const DAY = 86_400_000

/** Local date `days` from now as "YYYY-MM-DD". */
const dayFrom = (now: Date, days: number) => dateKey(new Date(now.getTime() + days * DAY))

/** A local time on a day `days` from now, as an ISO timestamp. */
function slotIso(now: Date, days: number, hhmm: string): string {
  const day = new Date(now.getTime() + days * DAY)
  day.setHours(Number(hhmm.slice(0, 2)), Number(hhmm.slice(3)), 0, 0)
  return day.toISOString()
}

export function sampleDonors(now: Date): Donor[] {
  const donor = (
    n: number,
    fullName: string,
    bloodGroup: Donor['bloodGroup'],
    extra: Partial<Donor> = {},
  ): Donor => ({
    id: `DNR-${String(n).padStart(5, '0')}`,
    fullName,
    bloodGroup,
    phone: `0300 000${String(n).padStart(4, '0')}`,
    email: `donor-${String(n)}@example.com`,
    lastDonationAt: null,
    eligible: true,
    ineligibleReason: '',
    eligibleFrom: null,
    hospitalId: 1,
    ...extra,
  })
  return [
    donor(1, 'Sample Donor A', 'O-'),
    donor(2, 'Sample Donor B', 'B+', { lastDonationAt: new Date(now.getTime() - 90 * DAY).toISOString() }),
    donor(3, 'Sample Donor C', 'A+', {
      eligible: false,
      ineligibleReason: 'Low haemoglobin',
      eligibleFrom: dayFrom(now, 20),
    }),
    donor(4, 'Sample Donor D', 'AB+', {
      eligible: false,
      ineligibleReason: 'Deferred after a travel screening',
      eligibleFrom: null,
    }),
    donor(5, 'Sample Donor E', 'O+', {
      eligible: false,
      lastDonationAt: new Date(now.getTime() - 26 * DAY).toISOString(),
      ineligibleReason: 'Donated on sample date; next eligible on sample date.',
      eligibleFrom: dayFrom(now, 30),
    }),
    donor(6, 'Sample Donor F', 'A-'),
  ]
}

/** Units linked to a donor, for the donor panel. Keyed by donor code. */
export function sampleDonorUnits(now: Date): Record<string, BloodUnit[]> {
  const collected = new Date(now.getTime() - 90 * DAY).toISOString()
  const expires = new Date(now.getTime() - 48 * DAY).toISOString()
  return {
    'DNR-00002': [
      {
        id: 'G7731 26 900201',
        group: 'B+',
        component: 'redCells',
        collectedAt: collected,
        expiresAt: expires,
        status: 'expired',
        location: 'Blood fridge 1',
      },
    ],
  }
}

/** Two bookings at hospital 1: one for Sample Donor F tomorrow, and one for another donor on the day after. */
export function sampleAppointments(now: Date): Appointment[] {
  return [
    {
      id: 1,
      donorId: 'DNR-00006',
      donorName: 'Sample Donor F',
      startsAt: slotIso(now, 1, '10:00'),
      slotMinutes: 30,
      status: 'booked',
      hospitalId: 1,
    },
    {
      id: 2,
      donorId: 'DNR-00001',
      donorName: 'Sample Donor A',
      startsAt: slotIso(now, 2, '14:00'),
      slotMinutes: 30,
      status: 'booked',
      hospitalId: 1,
    },
  ]
}
