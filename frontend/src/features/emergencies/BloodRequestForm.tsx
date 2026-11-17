import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { BLOOD_GROUPS, COMPONENTS, type BloodGroup, type Component } from '../../api/blood'
import { ApiError } from '../../api/client'
import { createCase, MAX_QUANTITY, SEVERITIES, type Severity } from '../../api/emergencies'
import { Button } from '../../components/form/Button'
import { Field, FieldError } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { formatGroup } from '../blood/blood'
import {
  bloodRequestErrors,
  emptyBloodRequest,
  toBloodRequest,
  validateBloodRequest,
  type BloodRequestErrors,
  type BloodRequestValues,
} from './emergencies'
import styles from './Emergencies.module.css'

const FIX_FIELDS = 'The request wasn’t sent. Fix the fields marked below.'

/** Where focus goes for the first error: the urgency choice, then the fields in order. */
function focusFirstError(errors: BloodRequestErrors) {
  const target = errors.severity
    ? `urgency-${SEVERITIES[0].id}`
    : errors.group
      ? 'blood-group'
      : errors.component
        ? 'blood-component'
        : errors.quantity
          ? 'blood-quantity'
          : undefined
  if (target) document.getElementById(target)?.focus()
}

const hasError = (errors: BloodRequestErrors) => Object.values(errors).some(Boolean)

/**
 * "Request blood" (story #36): one step, one blood need and its urgency. Opens a case through the same endpoint
 * as the full form, then shows that case. The server's field errors show on their fields.
 */
export function BloodRequestForm({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const [values, setValues] = useState<BloodRequestValues>(emptyBloodRequest)
  const [errors, setErrors] = useState<BloodRequestErrors>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)

  useEffect(() => {
    document.getElementById(`urgency-${SEVERITIES[0].id}`)?.focus()
  }, [])

  const update = (change: Partial<BloodRequestValues>, field: keyof BloodRequestErrors) => {
    setValues((v) => ({ ...v, ...change }))
    setErrors((e) => ({ ...e, [field]: undefined }))
  }

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = validateBloodRequest(values)
    setErrors(found)
    if (hasError(found)) {
      setAlert(FIX_FIELDS)
      focusFirstError(found)
      return
    }
    setAlert(undefined)
    setPending(true)
    try {
      const created = await createCase(toBloodRequest(values))
      navigate(`/staff/emergencies/${encodeURIComponent(created.id)}`)
    } catch (error) {
      setPending(false)
      const status = error instanceof ApiError ? error.status : 0
      const server = bloodRequestErrors(error)
      if (status === 400 && hasError(server)) {
        setErrors(server)
        setAlert(server.form ?? FIX_FIELDS)
        focusFirstError(server)
      } else if (status === 403) {
        setAlert('Your role can’t send blood requests.')
      } else {
        setAlert('The hospital’s system didn’t respond, so the request wasn’t sent. Try again.')
      }
    }
  }

  return (
    <Panel title="Request blood">
      <form className={styles.form} onSubmit={send} noValidate>
        <fieldset className={styles.fieldset} aria-describedby={errors.severity ? 'urgency-error' : undefined}>
          <legend>Urgency</legend>
          <div className={styles.severities}>
            {SEVERITIES.map((s) => (
              <label key={s.id} className={styles.severity} data-severity={s.id}>
                <input
                  id={`urgency-${s.id}`}
                  type="radio"
                  name="urgency"
                  value={s.id}
                  checked={values.severity === s.id}
                  onChange={() => update({ severity: s.id as Severity }, 'severity')}
                />
                <span>
                  <strong>{s.label}</strong>
                  <span className={styles.hint}>{s.hint}</span>
                </span>
              </label>
            ))}
          </div>
          <FieldError id="urgency">{errors.severity}</FieldError>
        </fieldset>

        <div className={styles.needFields}>
          <Field id="blood-group" label="Blood group" error={errors.group}>
            <select
              id="blood-group"
              value={values.group}
              aria-describedby={errors.group ? 'blood-group-error' : undefined}
              onChange={(e) => update({ group: e.target.value as BloodGroup }, 'group')}
            >
              {BLOOD_GROUPS.map((g) => (
                <option key={g} value={g}>
                  {formatGroup(g)}
                </option>
              ))}
            </select>
          </Field>
          <Field id="blood-component" label="Component" error={errors.component}>
            <select
              id="blood-component"
              value={values.component}
              aria-describedby={errors.component ? 'blood-component-error' : undefined}
              onChange={(e) => update({ component: e.target.value as Component }, 'component')}
            >
              {COMPONENTS.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </Field>
          <TextField
            id="blood-quantity"
            label="Units"
            type="number"
            min={1}
            max={MAX_QUANTITY.blood}
            hint={`Whole units, 1 to ${MAX_QUANTITY.blood} per request`}
            value={values.quantity}
            onChange={(quantity) => update({ quantity }, 'quantity')}
            error={errors.quantity}
          />
        </div>

        <FormAlert>{alert}</FormAlert>
        <div className={styles.actions}>
          <Button pending={pending} pendingLabel="Sending…">
            Send request
          </Button>
          <button type="button" className={styles.link} onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  )
}
