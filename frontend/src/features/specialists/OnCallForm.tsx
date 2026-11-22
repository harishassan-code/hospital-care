import { useState, type FormEvent } from 'react'
import { ApiError, fieldErrors } from '../../api/client'
import { addOnCallWindow, type OnCallWindow } from '../../api/specialists'
import { Button } from '../../components/form/Button'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import styles from '../blood/Blood.module.css'
import { karachiIso } from './schedule'

type FieldKey = 'startDate' | 'startTime' | 'endDate' | 'endTime'
const ORDER: FieldKey[] = ['startDate', 'startTime', 'endDate', 'endTime']
const INPUT_ID: Record<FieldKey, string> = {
  startDate: 'window-start-date',
  startTime: 'window-start-time',
  endDate: 'window-end-date',
  endTime: 'window-end-time',
}
const EMPTY: Record<FieldKey, string> = { startDate: '', startTime: '', endDate: '', endTime: '' }

/**
 * Adds an on-call window (story #62). Start and end each take a day and a clock time, Karachi time, so an overnight
 * window is one entry. The server's overlap and "already ended" answers appear on the field they name.
 */
export function OnCallForm({ specialistId, onAdded }: { specialistId: number; onAdded: (window: OnCallWindow) => void }) {
  const [values, setValues] = useState(EMPTY)
  const [errors, setErrors] = useState<Partial<Record<FieldKey, string>>>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)

  const set = (key: FieldKey) => (value: string) => {
    setValues((v) => ({ ...v, [key]: value }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  /** Put the cursor on the first field with an error. */
  const focusFirst = (form: HTMLFormElement, found: Partial<Record<FieldKey, string>>) => {
    const first = ORDER.find((key) => found[key])
    if (first) form.querySelector<HTMLElement>(`#${INPUT_ID[first]}`)?.focus()
    return first
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const found: Partial<Record<FieldKey, string>> = {}
    if (!values.startDate) found.startDate = 'Pick the day it starts.'
    if (!values.startTime) found.startTime = 'Pick the start time.'
    if (!values.endDate) found.endDate = 'Pick the day it ends.'
    if (!values.endTime) found.endTime = 'Pick the end time.'
    const startsAt = values.startDate && values.startTime ? karachiIso(values.startDate, values.startTime) : ''
    const endsAt = values.endDate && values.endTime ? karachiIso(values.endDate, values.endTime) : ''
    if (startsAt && endsAt && Date.parse(endsAt) <= Date.parse(startsAt)) {
      found.endTime = 'The on-call time must end after it starts.'
    }
    setErrors(found)
    setAlert(undefined)
    if (focusFirst(form, found)) {
      setAlert('The on-call time wasn’t saved. Fix the fields marked above.')
      return
    }

    setPending(true)
    try {
      const window = await addOnCallWindow(specialistId, { startsAt, endsAt })
      setValues(EMPTY)
      onAdded(window)
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      const server = fieldErrors(error)
      const onFields: Partial<Record<FieldKey, string>> = {}
      if (server.startsAt) onFields.startTime = server.startsAt
      if (server.endsAt) onFields.endTime = server.endsAt
      setErrors(onFields)
      if (status === 400 && focusFirst(form, onFields)) {
        setAlert('The on-call time wasn’t saved. Fix the fields marked above.')
      } else if (status === 403) {
        setAlert(server.detail ?? 'Your role can’t change on-call times.')
      } else {
        setAlert('The hospital’s system didn’t respond, so the on-call time wasn’t saved. Try again.')
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate aria-label="Add an on-call time">
      <div className={styles.pair}>
        <TextField
          id={INPUT_ID.startDate}
          label="Start date"
          type="date"
          value={values.startDate}
          onChange={set('startDate')}
          error={errors.startDate}
        />
        <TextField
          id={INPUT_ID.startTime}
          label="Start time"
          type="time"
          value={values.startTime}
          onChange={set('startTime')}
          error={errors.startTime}
        />
      </div>
      <div className={styles.pair}>
        <TextField
          id={INPUT_ID.endDate}
          label="End date"
          type="date"
          hint="For an overnight window, the day it ends."
          value={values.endDate}
          onChange={set('endDate')}
          error={errors.endDate}
        />
        <TextField
          id={INPUT_ID.endTime}
          label="End time"
          type="time"
          value={values.endTime}
          onChange={set('endTime')}
          error={errors.endTime}
        />
      </div>
      {alert && <FormAlert>{alert}</FormAlert>}
      <div className={styles.formActions}>
        <Button pending={pending} pendingLabel="Adding…">
          Add on-call time
        </Button>
      </div>
    </form>
  )
}
