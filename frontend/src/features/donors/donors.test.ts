import { describe, expect, it } from 'vitest'
import type { Appointment } from '../../api/donors'
import { at } from '../../test/clock'
import { sampleDonors } from '../../test/fixtures/donors'
import {
  bookedStarts,
  bookingHospitalId,
  eligibilityLabel,
  firstBookableDay,
  formatSlot,
  slotState,
  slotStart,
  slotTimes,
} from './donors'
import { emptyDonor, emptyScreening, toDonorInput, validateDonor, validateScreening } from './validation'

const now = at('15:00')
const [eligible, , deferred, noEnd] = sampleDonors(now)

describe('slots', () => {
  it('offers 08:00 to 17:00 every 30 minutes, both ends included', () => {
    const times = slotTimes()
    expect(times).toHaveLength(19)
    expect(times[0]).toBe('08:00')
    expect(times.at(-1)).toBe('17:00')
    expect(times).toContain('12:30')
  })

  it('marks a slot free, booked at this hospital, or passed', () => {
    const taken = new Set([slotStart('2026-10-06', '10:00').getTime()])
    expect(slotState(slotStart('2026-10-06', '10:30'), taken, now)).toBe('free')
    expect(slotState(slotStart('2026-10-06', '10:00'), taken, now)).toBe('booked')
    // 15:00 is "now", so it has passed
    expect(slotState(slotStart('2026-10-05', '14:30'), taken, now)).toBe('passed')
    expect(slotState(slotStart('2026-10-05', '15:00'), taken, now)).toBe('passed')
  })

  it('counts only booked slots at the hospital a booking would go to', () => {
    const appointments: Appointment[] = [
      { id: 1, donorId: 'DNR-00001', donorName: 'A', startsAt: slotStart('2026-10-06', '10:00').toISOString(), slotMinutes: 30, status: 'booked', hospitalId: 1 },
      { id: 2, donorId: 'DNR-00002', donorName: 'B', startsAt: slotStart('2026-10-06', '11:00').toISOString(), slotMinutes: 30, status: 'booked', hospitalId: 2 },
      { id: 3, donorId: 'DNR-00003', donorName: 'C', startsAt: slotStart('2026-10-06', '12:00').toISOString(), slotMinutes: 30, status: 'cancelled', hospitalId: 1 },
    ]
    expect([...bookedStarts(appointments, 1)]).toEqual([slotStart('2026-10-06', '10:00').getTime()])
    expect(bookedStarts(appointments, 3).size).toBe(0)
  })

  it('books at the actor’s hospital, else the donor’s, as the server does', () => {
    expect(bookingHospitalId(4, { ...eligible, hospitalId: 9 })).toBe(4)
    expect(bookingHospitalId(null, { ...eligible, hospitalId: 9 })).toBe(9)
  })

  it('formats a booked time for the status message', () => {
    expect(formatSlot(slotStart('2026-10-06', '10:30').toISOString())).toBe('6 Oct 2026, 10:30')
  })
})

describe('eligibility', () => {
  it('says eligible, not eligible until a day, or not eligible with no end date', () => {
    expect(eligibilityLabel(eligible)).toBe('Eligible')
    expect(eligibilityLabel(deferred)).toBe('Not eligible until 25 Oct 2026')
    expect(eligibilityLabel(noEnd)).toBe('Not eligible, no end date')
  })

  it('finds the first day a donor can be booked, or none for a permanent deferral', () => {
    expect(firstBookableDay(eligible, '2026-10-05')).toBe('2026-10-05')
    expect(firstBookableDay(deferred, '2026-10-05')).toBe('2026-10-25')
    expect(firstBookableDay(noEnd, '2026-10-05')).toBeNull()
  })
})

describe('donor form validation', () => {
  const valid = { fullName: 'Sample Donor Z', bloodGroup: 'O-' as const, phone: '', email: '' }

  it('needs a name of at most 150 characters and a blood group', () => {
    expect(validateDonor(emptyDonor())).toEqual({ fullName: 'Enter the donor’s full name', bloodGroup: 'Choose a blood group' })
    expect(validateDonor({ ...valid, fullName: 'x'.repeat(151) }).fullName).toBe('Use at most 150 characters')
    expect(validateDonor(valid)).toEqual({})
  })

  it('checks the phone the way the API does: 7 to 20 digits, spaces, dashes, optional leading +', () => {
    expect(validateDonor({ ...valid, phone: '+92 300-1234567' })).toEqual({})
    expect(validateDonor({ ...valid, phone: '12345' }).phone).toBeDefined()
    expect(validateDonor({ ...valid, phone: 'call me' }).phone).toBeDefined()
  })

  it('checks an email only when one is given', () => {
    expect(validateDonor({ ...valid, email: '' })).toEqual({})
    expect(validateDonor({ ...valid, email: 'donor@example' }).email).toBeDefined()
    expect(validateDonor({ ...valid, email: 'donor@example.com' })).toEqual({})
  })

  it('trims the request and leaves out empty optional fields', () => {
    expect(toDonorInput({ ...valid, fullName: '  Sample Donor Z ', phone: ' ', email: '' })).toEqual({
      fullName: 'Sample Donor Z',
      bloodGroup: 'O-',
    })
  })
})

describe('screening validation', () => {
  const today = '2026-10-05'

  it('needs a choice, and for not eligible a reason and an end date or no end date', () => {
    expect(validateScreening(emptyScreening(), today).eligible).toBeDefined()
    expect(validateScreening({ ...emptyScreening(), eligible: 'yes' }, today)).toEqual({})
    const no = { ...emptyScreening(), eligible: 'no' as const }
    expect(validateScreening(no, today)).toEqual({
      reason: 'Enter the reason. Keep it short and leave out names',
      endDate: 'Choose an end date, or tick No end date',
    })
    expect(validateScreening({ ...no, reason: 'Low haemoglobin', noEndDate: true }, today)).toEqual({})
  })

  it('needs an end date after today', () => {
    const base = { ...emptyScreening(), eligible: 'no' as const, reason: 'Low haemoglobin' }
    expect(validateScreening({ ...base, endDate: today }, today).endDate).toBe('The end date must be after today')
    expect(validateScreening({ ...base, endDate: '2026-10-06' }, today)).toEqual({})
  })
})
