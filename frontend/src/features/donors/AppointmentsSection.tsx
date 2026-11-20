import { useCallback, useState } from 'react'
import { cancelAppointment, listAppointments, type Appointment, type Donor } from '../../api/donors'
import { Button } from '../../components/form/Button'
import { FormAlert } from '../../components/form/FormAlert'
import { useLoad } from '../../lib/useLoad'
import { BookAppointment } from './BookAppointment'
import { DonorSection } from './DonorSection'
import styles from './Donors.module.css'
import { formatSlot, serverDetail, statusOf } from './donors'

const byStart = (a: Appointment, b: Appointment) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime()

type Props = {
  donor: Donor
  canWrite: boolean
}

/** The donor's upcoming appointments, each with Cancel (behind a confirmation), and the booking form (story #22). */
export function AppointmentsSection({ donor, canWrite }: Props) {
  const { result, setData } = useLoad(listAppointments)
  const [confirming, setConfirming] = useState<number>()
  const [busy, setBusy] = useState<number>()
  const [alert, setAlert] = useState<string>()
  const [status, setStatus] = useState('')

  const reload = useCallback(() => {
    listAppointments()
      .then((fresh) => setData(() => fresh))
      .catch(() => undefined)
  }, [setData])

  if (result.state === 'failed') {
    return (
      <DonorSection title="Appointments">
        <p role="alert">Couldn’t load appointments. Reload the page to try again.</p>
      </DonorSection>
    )
  }
  if (result.state === 'loading') {
    return (
      <DonorSection title="Appointments">
        <p role="status">Loading appointments…</p>
      </DonorSection>
    )
  }

  const appointments = result.data
  const upcoming = appointments.filter((a) => a.donorId === donor.id && a.status === 'booked').sort(byStart)

  async function cancel(appointment: Appointment) {
    setBusy(appointment.id)
    setAlert(undefined)
    setStatus('')
    try {
      await cancelAppointment(appointment.id)
      setData((list) => list.filter((a) => a.id !== appointment.id))
      setConfirming(undefined)
      setStatus(`Cancelled the appointment for ${formatSlot(appointment.startsAt)}.`)
    } catch (error) {
      const code = statusOf(error)
      if (code === 409) {
        setConfirming(undefined)
        setAlert(serverDetail(error) ?? 'This appointment is already cancelled.')
        reload()
      } else if (code === 403) {
        setAlert(serverDetail(error) ?? 'Your role can’t cancel this appointment.')
      } else {
        setAlert('The hospital’s system didn’t respond, so the appointment wasn’t cancelled. Try again.')
      }
    } finally {
      setBusy(undefined)
    }
  }

  return (
    <DonorSection title="Appointments">
      <FormAlert>{alert}</FormAlert>
      <p role="status">{status}</p>
      {upcoming.length === 0 ? (
        <p className={styles.note}>No upcoming appointments for this donor.</p>
      ) : (
        <ul className={styles.list}>
          {upcoming.map((appointment) => (
            <li key={appointment.id}>
              <span>{formatSlot(appointment.startsAt)}</span>
              {canWrite &&
                (confirming === appointment.id ? (
                  <span className={styles.inline}>
                    <Button type="button" pending={busy === appointment.id} pendingLabel="Cancelling…" onClick={() => cancel(appointment)}>
                      Confirm cancel
                    </Button>
                    <button type="button" className={styles.back} onClick={() => setConfirming(undefined)}>
                      Keep it
                    </button>
                  </span>
                ) : (
                  <button type="button" onClick={() => setConfirming(appointment.id)}>
                    Cancel
                  </button>
                ))}
            </li>
          ))}
        </ul>
      )}
      {canWrite && (
        <BookAppointment
          donor={donor}
          appointments={appointments}
          onBooked={(booked) => setData((list) => [...list, booked])}
          onReload={reload}
        />
      )}
    </DonorSection>
  )
}
