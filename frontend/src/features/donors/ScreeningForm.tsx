import { useState, type FormEvent } from 'react'
import { fieldErrors } from '../../api/client'
import { recordScreening, type Donor } from '../../api/donors'
import { Button } from '../../components/form/Button'
import { Checkbox } from '../../components/form/Checkbox'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Field } from '../../components/form/Field'
import { firstErrorKey, type FieldErrors } from '../auth/validation'
import { useStaff } from '../staff/staffContext'
import { dateKey } from '../../lib/time'
import styles from './Donors.module.css'
import { eligibilityLabel, statusOf } from './donors'
import {
  emptyScreening,
  SCREENING_FIELD_ORDER,
  validateScreening,
  type ScreeningField,
  type ScreeningFormValues,
} from './validation'

/** The element to focus for each field. The eligibility group focuses its first choice. */
const FOCUS_ID: Record<ScreeningField, string> = {
  eligible: 'screening-eligible-yes',
  reason: 'screening-reason',
  endDate: 'screening-end',
}

const END_HINT = 'Pick a day after today, or tick No end date.'

type Props = {
  donor: Donor
  onSaved: (donor: Donor) => void
}

/**
 * Record eligibility (story #21): eligible, or not eligible with a reason and either an end date or a permanent
 * deferral. Saving eligible clears any deferral. The server's answer replaces the donor shown.
 */
export function ScreeningForm({ donor, onSaved }: Props) {
  const { now } = useStaff()
  const today = dateKey(now)
  const [values, setValues] = useState<ScreeningFormValues>(emptyScreening)
  const [errors, setErrors] = useState<FieldErrors<ScreeningField>>({})
  const [alert, setAlert] = useState<string>()
  const [status, setStatus] = useState('')
  const [pending, setPending] = useState(false)

  const set =
    <K extends keyof ScreeningFormValues>(key: K) =>
    (value: ScreeningFormValues[K]) => {
      setValues((v) => ({ ...v, [key]: value }))
      setErrors((e) => ({ ...e, [key]: undefined }))
    }

  const focusFirst = (found: FieldErrors<ScreeningField>) => {
    const first = firstErrorKey(found, SCREENING_FIELD_ORDER)
    if (first) document.getElementById(FOCUS_ID[first])?.focus()
    return first
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAlert(undefined)
    setStatus('')
    const found = validateScreening(values, today)
    setErrors(found)
    if (focusFirst(found)) {
      setAlert('The screening wasn’t saved. Fix the fields marked above.')
      return
    }

    const input =
      values.eligible === 'yes'
        ? { eligible: true }
        : { eligible: false, reason: values.reason.trim(), deferredUntil: values.noEndDate ? null : values.endDate }
    setPending(true)
    try {
      const saved = await recordScreening(donor.id, input)
      onSaved(saved)
      setValues(emptyScreening())
      setErrors({})
      setStatus(`Screening saved for ${saved.id}: ${eligibilityLabel(saved)}.`)
    } catch (error) {
      const code = statusOf(error)
      const server = fieldErrors(error)
      const onFields: FieldErrors<ScreeningField> = {}
      if (server.reason) onFields.reason = server.reason
      if (server.deferredUntil) onFields.endDate = server.deferredUntil
      setErrors(onFields)
      if (code === 403) {
        setAlert('Your role can’t screen donors.')
      } else if (code === 400) {
        focusFirst(onFields)
        setAlert('The screening wasn’t saved. Fix the fields marked above.')
      } else {
        setAlert('The hospital’s system didn’t respond, so the screening wasn’t saved. Try again.')
      }
    } finally {
      setPending(false)
    }
  }

  const notEligible = values.eligible === 'no'

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate aria-label={`Screening for ${donor.id}`}>
      <fieldset className={styles.fieldset} aria-describedby={errors.eligible ? 'screening-eligible-error' : undefined}>
        <legend>Eligibility</legend>
        <div>
          <label className={styles.choice}>
            <input
              id="screening-eligible-yes"
              type="radio"
              name="screening-eligible"
              checked={values.eligible === 'yes'}
              onChange={() => set('eligible')('yes')}
            />
            Eligible
          </label>
          <label className={styles.choice}>
            <input
              id="screening-eligible-no"
              type="radio"
              name="screening-eligible"
              checked={values.eligible === 'no'}
              onChange={() => set('eligible')('no')}
            />
            Not eligible
          </label>
        </div>
        {errors.eligible && (
          <p className={styles.note} id="screening-eligible-error" role="alert">
            {errors.eligible}
          </p>
        )}
      </fieldset>

      {notEligible && (
        <>
          <TextField
            id="screening-reason"
            label="Reason"
            hint="Required. Up to 300 characters. Keep it short and leave out names."
            value={values.reason}
            onChange={set('reason')}
            error={errors.reason}
            autoComplete="off"
          />
          <Field id="screening-end" label="Deferred until" hint={END_HINT} error={errors.endDate}>
            <input
              id="screening-end"
              type="date"
              min={today}
              value={values.endDate}
              disabled={values.noEndDate}
              aria-invalid={errors.endDate ? true : undefined}
              aria-describedby={errors.endDate ? 'screening-end-hint screening-end-error' : 'screening-end-hint'}
              onChange={(e) => set('endDate')(e.target.value)}
            />
          </Field>
          <Checkbox id="screening-no-end" checked={values.noEndDate} onChange={set('noEndDate')}>
            No end date (permanent deferral)
          </Checkbox>
        </>
      )}

      <FormAlert>{alert}</FormAlert>
      <p className={styles.note} role="status">
        {status}
      </p>
      <div className={styles.inline}>
        <Button pending={pending} pendingLabel="Saving…">
          Save screening
        </Button>
      </div>
    </form>
  )
}
