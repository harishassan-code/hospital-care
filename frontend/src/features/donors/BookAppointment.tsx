import { useState, type FormEvent } from 'react'
import { fieldErrors } from '../../api/client'
import { bookAppointment, type Appointment, type Donor } from '../../api/donors'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { dateKey } from '../../lib/time'
import { useStaff } from '../staff/staffContext'
import styles from './Donors.module.css'
import {
  bookedStarts,
  bookingHospitalId,
  firstBookableDay,
  formatDay,
  formatSlot,
  slotStart,
  slotState,
  slotTimes,
  statusOf,
  type SlotState,
} from './donors'

const STATE_TEXT: Record<SlotState, string> = { free: 'Free', booked: 'Booked', passed: 'Passed' }

type Props = {
  donor: Donor
  /** The hospital's upcoming bookings, from the list the panel loads. */
  appointments: readonly Appointment[]
  onBooked: (appointment: Appointment) => void
  /** Read the bookings again, e.g. when the server refused a slot someone else took first. */
  onReload: () => void
}

/**
 * Book a donation slot (story #22): pick a day, then a start time, then book. Times that are taken or have passed
 * are disabled. A donor with an upcoming appointment can't book another.
 */
export function BookAppointment({ donor, appointments, onBooked, onReload }: Props) {
  const { user, now } = useStaff()
  const today = dateKey(now)
  const earliest = firstBookableDay(donor, today)
  const [day, setDay] = useState(earliest ?? today)
  const [time, setTime] = useState('')
  const [pending, setPending] = useState(false)
  const [alert, setAlert] = useState<string>()
  const [status, setStatus] = useState('')

  if (earliest === null) return <p className={styles.blocked}>This donor can’t be booked.</p>

  const upcoming = appointments.find((a) => a.donorId === donor.id)
  const taken = bookedStarts(appointments, bookingHospitalId(user.hospital?.id ?? null, donor))
  const dayError = !day
    ? 'Choose a day.'
    : day < today
      ? 'Choose today or a later day.'
      : day < earliest
        ? `This donor can’t give blood before ${formatDay(earliest)}.`
        : undefined

  function changeDay(next: string) {
    setDay(next)
    setTime('')
    setAlert(undefined)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAlert(undefined)
    setStatus('')
    if (dayError) return setAlert(dayError)
    if (!time) return setAlert('Choose a start time.')

    setPending(true)
    try {
      const booked = await bookAppointment({ donorId: donor.id, startsAt: slotStart(day, time).toISOString() })
      onBooked(booked)
      setTime('')
      setStatus(`Booked ${donor.id} for ${formatSlot(booked.startsAt)}.`)
    } catch (error) {
      const code = statusOf(error)
      if (code === 400) {
        const server = fieldErrors(error)
        setAlert(server.startsAt ?? server.donorId ?? 'The appointment wasn’t booked. Choose another time.')
        onReload()
      } else if (code === 403) {
        setAlert('Your role can’t book this donor’s appointment.')
      } else {
        setAlert('The hospital’s system didn’t respond, so the appointment wasn’t booked. Try again.')
      }
    } finally {
      setPending(false)
    }
  }

  const blocked = upcoming !== undefined
  const dayInvalid = dayError !== undefined

  return (
    <form className={styles.form} onSubmit={submit} noValidate aria-label="Book a donation">
      {upcoming && (
        <p className={styles.blocked}>
          This donor already has an appointment on {formatSlot(upcoming.startsAt)}. Cancel it to book another.
        </p>
      )}
      <fieldset className={styles.fieldset} disabled={blocked}>
        <Field id="booking-day" label="Day" error={dayError}>
          <input
            id="booking-day"
            type="date"
            min={earliest}
            value={day}
            aria-invalid={dayInvalid ? true : undefined}
            aria-describedby={dayError ? 'booking-day-error' : undefined}
            onChange={(e) => changeDay(e.target.value)}
          />
        </Field>
        <fieldset className={styles.fieldset} disabled={dayInvalid}>
          <legend>Start time</legend>
          <div className={styles.slots} role="group" aria-label={`Start times on ${formatDay(day)}`}>
            {slotTimes().map((clock) => {
              const state = slotState(slotStart(day, clock), taken, now)
              return (
                <button
                  key={clock}
                  type="button"
                  className={styles.slot}
                  aria-label={`${clock}, ${state}`}
                  aria-pressed={time === clock}
                  disabled={state !== 'free'}
                  onClick={() => setTime(clock)}
                >
                  <span>{clock}</span>
                  <span className={styles.slotState}>{STATE_TEXT[state]}</span>
                </button>
              )
            })}
          </div>
        </fieldset>
        <FormAlert>{alert}</FormAlert>
        <p role="status">{status}</p>
        <div className={styles.inline}>
          <Button pending={pending} pendingLabel="Booking…" disabled={!time || dayInvalid}>
            Book appointment
          </Button>
        </div>
      </fieldset>
    </form>
  )
}
