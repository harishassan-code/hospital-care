import { useState, type FormEvent } from 'react'
import { ApiError, fieldErrors } from '../../api/client'
import { createOrBooking, HOSPITAL_UTC_OFFSET, type ScheduleRoom } from '../../api/operatingRooms'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import styles from '../blood/Blood.module.css'

/** The form's fields, in the order they appear. The server's field names map onto them below. */
type FieldKey = 'roomId' | 'date' | 'start' | 'end' | 'procedure' | 'surgeon' | 'patientInitials'
const ORDER: FieldKey[] = ['roomId', 'date', 'start', 'end', 'procedure', 'surgeon', 'patientInitials']
const INPUT_ID: Record<FieldKey, string> = {
  roomId: 'booking-room',
  date: 'booking-date',
  start: 'booking-start',
  end: 'booking-end',
  procedure: 'booking-procedure',
  surgeon: 'booking-surgeon',
  patientInitials: 'booking-initials',
}
const FROM_SERVER: Record<string, FieldKey> = {
  roomId: 'roomId',
  startsAt: 'start',
  endsAt: 'end',
  procedure: 'procedure',
  surgeon: 'surgeon',
  patientInitials: 'patientInitials',
}

type Values = Record<FieldKey, string>

/** "Book a slot" button that opens the form (story #29). Only shown to roles that can edit bookings. */
export function BookSlotForm({
  rooms,
  day,
  onBooked,
}: {
  rooms: readonly ScheduleRoom[]
  day: string
  onBooked: (day: string) => void
}) {
  const [open, setOpen] = useState(false)
  if (!open) {
    return (
      <button type="button" className={styles.more} onClick={() => setOpen(true)}>
        Book a slot
      </button>
    )
  }
  return (
    <Panel title="Book a slot">
      <SlotForm rooms={rooms} day={day} onBooked={onBooked} onClose={() => setOpen(false)} />
    </Panel>
  )
}

function SlotForm({
  rooms,
  day,
  onBooked,
  onClose,
}: {
  rooms: readonly ScheduleRoom[]
  day: string
  onBooked: (day: string) => void
  onClose: () => void
}) {
  const [values, setValues] = useState<Values>({
    roomId: rooms[0] ? String(rooms[0].id) : '',
    date: day,
    start: '',
    end: '',
    procedure: '',
    surgeon: '',
    patientInitials: '',
  })
  const [errors, setErrors] = useState<Partial<Record<FieldKey, string>>>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)

  const set = (key: FieldKey) => (value: string) => {
    setValues((v) => ({ ...v, [key]: value }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  /** Put the cursor on the first field with an error, as the other staff forms do. */
  const focusFirst = (form: HTMLFormElement, found: Partial<Record<FieldKey, string>>) => {
    const first = ORDER.find((key) => found[key])
    if (first) form.querySelector<HTMLElement>(`#${INPUT_ID[first]}`)?.focus()
    return first
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const found: Partial<Record<FieldKey, string>> = {}
    if (!values.roomId) found.roomId = 'Choose a room.'
    if (!values.date) found.date = 'Pick a date.'
    if (!values.start) found.start = 'Pick a start time.'
    if (!values.end) found.end = 'Pick an end time.'
    if (!values.procedure.trim()) found.procedure = 'Enter the procedure, e.g. Appendicectomy.'
    if (values.start && values.end && values.end <= values.start) found.end = 'The end time must be after the start time.'
    setErrors(found)
    setAlert(undefined)
    if (focusFirst(form, found)) {
      setAlert('The booking wasn’t saved. Fix the fields marked above.')
      return
    }

    setPending(true)
    try {
      await createOrBooking({
        roomId: Number(values.roomId),
        startsAt: `${values.date}T${values.start}:00${HOSPITAL_UTC_OFFSET}`,
        endsAt: `${values.date}T${values.end}:00${HOSPITAL_UTC_OFFSET}`,
        procedure: values.procedure.trim(),
        surgeon: values.surgeon.trim(),
        patientInitials: values.patientInitials.trim(),
      })
      onBooked(values.date)
      onClose()
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      const server = fieldErrors(error)
      const onFields: Partial<Record<FieldKey, string>> = {}
      for (const [key, message] of Object.entries(server)) {
        const field = FROM_SERVER[key]
        if (field) onFields[field] = message
      }
      setErrors(onFields)
      if (status === 400 && focusFirst(form, onFields)) setAlert('The booking wasn’t saved. Fix the fields marked above.')
      else if (status === 403) setAlert('Your role can’t book operating room slots.')
      else setAlert('The hospital’s system didn’t respond, so the booking wasn’t saved. Try again.')
    } finally {
      setPending(false)
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <Field id={INPUT_ID.roomId} label="Room" error={errors.roomId}>
        <select id={INPUT_ID.roomId} value={values.roomId} onChange={(e) => set('roomId')(e.target.value)}>
          {rooms.map((room) => (
            <option key={room.id} value={room.id}>
              {room.name}
            </option>
          ))}
        </select>
      </Field>
      <TextField id={INPUT_ID.date} label="Date" type="date" value={values.date} onChange={set('date')} error={errors.date} />
      <TextField id={INPUT_ID.start} label="Start time" type="time" value={values.start} onChange={set('start')} error={errors.start} />
      <TextField id={INPUT_ID.end} label="End time" type="time" value={values.end} onChange={set('end')} error={errors.end} />
      <TextField
        id={INPUT_ID.procedure}
        label="Procedure"
        value={values.procedure}
        onChange={set('procedure')}
        error={errors.procedure}
        autoComplete="off"
      />
      <TextField
        id={INPUT_ID.surgeon}
        label="Surgeon"
        optional
        value={values.surgeon}
        onChange={set('surgeon')}
        error={errors.surgeon}
        autoComplete="off"
      />
      <TextField
        id={INPUT_ID.patientInitials}
        label="Patient initials"
        optional
        hint="Initials only, e.g. A.K."
        value={values.patientInitials}
        onChange={set('patientInitials')}
        error={errors.patientInitials}
        autoComplete="off"
      />
      {alert && <FormAlert>{alert}</FormAlert>}
      <div className={styles.formActions}>
        <Button pending={pending} pendingLabel="Booking…">
          Book slot
        </Button>
        <button type="button" className={styles.more} onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  )
}
