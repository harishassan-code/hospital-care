import { useCallback, useState } from 'react'
import { ApiError } from '../../api/client'
import {
  cancelOrBooking,
  getOperatingRoomSchedule,
  OR_STATUSES,
  type OrBooking,
  type ScheduleRoom,
} from '../../api/operatingRooms'
import { ButtonLink } from '../../components/form/Button'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import bedStyles from '../../features/beds/Beds.module.css'
import { BookSlotForm } from '../../features/operatingRooms/BookSlotForm'
import { clockTime, ROOM_TONE, slotRange } from '../../features/operatingRooms/operatingRooms'
import styles from '../../features/operatingRooms/Schedule.module.css'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { dateKey } from '../../lib/time'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

const DAY = /^\d{4}-\d{2}-\d{2}$/
const NO_RESPONSE = 'The hospital’s system didn’t respond, so the booking wasn’t cancelled. Try again.'
const statusLabel = (status: ScheduleRoom['status']) => OR_STATUSES.find((s) => s.value === status)!.label

/** Operating rooms by day (story #29): each room's booked slots, a day picker, and booking and cancelling. */
export default function OperatingRoomSchedulePage() {
  const { role } = useStaff()
  // `query` is what is loaded. A new object reloads it, which is how a save refreshes the day.
  const [query, setQuery] = useState(() => ({ day: dateKey(new Date()) }))
  // `draft` is what the date box shows, so a half-typed date doesn't reload anything.
  const [draft, setDraft] = useState(query.day)
  const load = useCallback(() => getOperatingRoomSchedule(query.day), [query])
  const { result } = useLoad(load)
  const [busyId, setBusyId] = useState<number>()
  const [announcement, setAnnouncement] = useState('')
  const [error, setError] = useState<string>()

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const { rooms } = result.data
  const editable = canEdit(role, 'orBookings')
  const reload = (day = query.day) => setQuery({ day })

  const changeDay = (value: string) => {
    setDraft(value)
    if (DAY.test(value)) setQuery({ day: value })
  }

  const cancel = async (room: ScheduleRoom, booking: OrBooking) => {
    if (!window.confirm(`Cancel ${booking.procedure} in ${room.name}, ${slotRange(booking.startsAt, booking.endsAt)}?`)) return
    setBusyId(booking.id)
    setError(undefined)
    try {
      await cancelOrBooking(booking.id)
      setAnnouncement(`${booking.procedure} in ${room.name} is cancelled`)
      reload()
    } catch (err) {
      setError(`${room.name}: ${await cancelFailure(err)}`)
      if (err instanceof ApiError && err.status === 409) reload()
    } finally {
      setBusyId(undefined)
    }
  }

  return (
    <div className={pageStyles.stack}>
      <Panel
        title="Day schedule"
        aside={
          <ButtonLink to="/staff/operating-rooms" variant="secondary">
            All operating rooms
          </ButtonLink>
        }
      >
        <div className={pageStyles.toolbar}>
          <TextField id="schedule-day" label="Day" type="date" value={draft} onChange={changeDay} />
        </div>
      </Panel>
      {editable && (
        <BookSlotForm
          rooms={rooms}
          day={query.day}
          onBooked={(booked) => {
            setDraft(booked)
            reload(booked)
            setAnnouncement('Slot booked')
          }}
        />
      )}
      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {announcement}
      </p>
      {rooms.length === 0 && <p>No operating rooms registered yet.</p>}
      {rooms.map((room) => (
        <Panel
          key={room.id}
          title={room.name}
          aside={<StatusBadge tone={ROOM_TONE[room.status]}>{statusLabel(room.status)}</StatusBadge>}
        >
          {room.bookings.length === 0 ? (
            <p>No bookings in {room.name} on this day.</p>
          ) : (
            <ol className={styles.list} aria-label={`Bookings in ${room.name}`}>
              {room.bookings.map((booking) => (
                <li key={booking.id} className={styles.booking}>
                  <p className={styles.slot}>
                    <time>{slotRange(booking.startsAt, booking.endsAt)}</time>
                    <strong>{booking.procedure}</strong>
                  </p>
                  <p className={styles.meta}>{bookingMeta(booking)}</p>
                  {editable && booking.canCancel && (
                    <button
                      type="button"
                      className={bedStyles.action}
                      aria-label={`Cancel ${booking.procedure} in ${room.name} at ${clockTime(booking.startsAt)}`}
                      disabled={busyId === booking.id}
                      onClick={() => cancel(room, booking)}
                    >
                      Cancel booking
                    </button>
                  )}
                </li>
              ))}
            </ol>
          )}
        </Panel>
      ))}
    </div>
  )
}

/** "Dr. Bilal Ahmed · Patient A.K. · booked by Hina Javed", leaving out what isn't known. */
function bookingMeta(booking: OrBooking): string {
  const parts = [
    booking.surgeon,
    booking.patientInitials && `Patient ${booking.patientInitials}`,
    booking.bookedBy && `booked by ${booking.bookedBy}`,
  ]
  return parts.filter(Boolean).join(' · ')
}

/** Why a cancel failed. A 409 means it was cancelled already, so the day is reloaded to show that. */
async function cancelFailure(error: unknown): Promise<string> {
  if (!(error instanceof ApiError)) return NO_RESPONSE
  if (error.status === 403) return 'Your role can’t cancel bookings.'
  if (error.status === 409) return 'That booking was already cancelled. The schedule shows the latest.'
  return NO_RESPONSE
}
