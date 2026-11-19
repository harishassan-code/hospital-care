import { useState, type FormEvent } from 'react'
import { ApiError, fieldErrors } from '../../api/client'
import {
  AMBULANCE_STATUSES,
  AMBULANCE_TYPES,
  registerAmbulance,
  type Ambulance,
  type AmbulanceInput,
} from '../../api/ambulances'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import styles from '../blood/Blood.module.css'

type FieldName = 'identifier' | 'type' | 'status'
const EMPTY: AmbulanceInput = { identifier: '', type: 'basic', status: 'available' }

export function RegisterAmbulanceForm({ onRegistered }: { onRegistered: (item: Ambulance) => void }) {
  const [open, setOpen] = useState(false)
  if (!open) {
    return (
      <button type="button" className={styles.more} onClick={() => setOpen(true)}>
        Register ambulance
      </button>
    )
  }
  return <AmbulanceForm onRegistered={onRegistered} onClose={() => setOpen(false)} />
}

function AmbulanceForm({ onRegistered, onClose }: { onRegistered: (item: Ambulance) => void; onClose: () => void }) {
  const [values, setValues] = useState<AmbulanceInput>(EMPTY)
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)

  const set = (key: FieldName) => (value: string) => {
    setValues((v) => ({ ...v, [key]: value }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!values.identifier.trim()) {
      setErrors({ identifier: 'Enter the call sign, e.g. AMB-12.' })
      return
    }
    setPending(true)
    setAlert(undefined)
    try {
      const saved = await registerAmbulance(values)
      onRegistered(saved)
      onClose()
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setErrors(fieldErrors(err) as Partial<Record<FieldName, string>>)
        setAlert('The ambulance wasn’t registered. Fix the fields marked above.')
      } else if (err instanceof ApiError && err.status === 403) {
        setAlert('Your role can’t register ambulances.')
      } else {
        setAlert('The hospital’s system didn’t respond, so the ambulance wasn’t registered. Try again.')
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title="Register ambulance">
      <FormAlert>{alert}</FormAlert>
      <form onSubmit={handleSubmit} noValidate>
        <TextField
          id="amb-identifier"
          label="Call sign"
          value={values.identifier}
          onChange={set('identifier')}
          error={errors.identifier}
          hint="e.g. AMB-12. Unique within your hospital."
        />
        <Field id="amb-type" label="Type" error={errors.type}>
          <select id="amb-type" value={values.type} onChange={(e) => set('type')(e.target.value)}>
            {AMBULANCE_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </Field>
        <Field id="amb-status" label="Status" error={errors.status}>
          <select id="amb-status" value={values.status ?? 'available'} onChange={(e) => set('status')(e.target.value)}>
            {AMBULANCE_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>
        <div className={styles.formActions}>
          <Button type="submit" disabled={pending} aria-busy={pending}>
            Register ambulance
          </Button>
          <button type="button" className={styles.linkButton} onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  )
}