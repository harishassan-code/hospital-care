import { useState, type FormEvent } from 'react'
import { createAmbulance, AMBULANCE_TYPES, type Ambulance, type AmbulanceInput, type AmbulanceType } from '../../api/ambulances'
import { ApiError, fieldErrors } from '../../api/client'
import { getHospitals } from '../../api/hospitals'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { useLoad } from '../../lib/useLoad'
import styles from '../blood/Blood.module.css'
import { useStaff } from '../staff/staffContext'

type FieldName = 'identifier' | 'type' | 'hospitalId'
const ORDER: FieldName[] = ['identifier', 'type', 'hospitalId']
const INVALID = 'The ambulance wasn’t registered. Fix the fields marked above.'

/** "Register ambulance" button that opens into the form (story #50). Editors only. */
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
  const { role, user } = useStaff()
  const admin = role === 'admin'
  // Admins pick the base hospital; it starts on their own. Everyone else registers at their own hospital.
  const [values, setValues] = useState({ identifier: '', type: 'basic' as AmbulanceType, hospitalId: String(user.hospital?.id ?? '') })
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)

  const set = (key: FieldName) => (value: string) => {
    setValues((v) => ({ ...v, [key]: value }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const found: Partial<Record<FieldName, string>> = {}
    if (!values.identifier.trim()) found.identifier = 'Enter the asset tag, e.g. AMB-04.'
    if (admin && !values.hospitalId) found.hospitalId = 'Pick the base hospital.'
    const focusFirst = (errs: typeof found) => {
      const first = ORDER.find((k) => errs[k])
      if (first) (form.elements.namedItem(first) as HTMLElement | null)?.focus()
      return first
    }
    setErrors(found)
    setAlert(undefined)
    if (focusFirst(found)) {
      setAlert(INVALID)
      return
    }

    const input: AmbulanceInput = { identifier: values.identifier.trim(), type: values.type }
    if (admin) input.hospitalId = Number(values.hospitalId)
    setPending(true)
    try {
      onRegistered(await createAmbulance(input))
      onClose()
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      const server = fieldErrors(error)
      const onFields: typeof found = {}
      for (const key of ORDER) if (server[key]) onFields[key] = server[key]
      setErrors(onFields)
      if (status === 400 && focusFirst(onFields)) setAlert(INVALID)
      else if (status === 403) setAlert('Your role can’t register ambulances.')
      else setAlert('The hospital’s system didn’t respond, so the ambulance wasn’t registered. Try again.')
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title="Register ambulance">
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <TextField
          id="identifier"
          label="Asset tag"
          hint="The number on the vehicle, e.g. AMB-04."
          value={values.identifier}
          onChange={set('identifier')}
          error={errors.identifier}
          autoComplete="off"
        />
        <div className={styles.pair}>
          <Field id="type" label="Type" error={errors.type}>
            <select id="type" value={values.type} onChange={(e) => set('type')(e.target.value)}>
              {AMBULANCE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>
          {admin && <BaseHospitalField value={values.hospitalId} onChange={set('hospitalId')} error={errors.hospitalId} />}
        </div>
        {alert && <FormAlert>{alert}</FormAlert>}
        <div className={styles.formActions}>
          <Button pending={pending} pendingLabel="Registering…">
            Register ambulance
          </Button>
          <button type="button" className={styles.more} onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  )
}

/** The base hospital select, for admins. Loads the network's hospitals only when it is shown. */
function BaseHospitalField({ value, onChange, error }: { value: string; onChange: (value: string) => void; error?: string }) {
  const { result } = useLoad(getHospitals)
  const ready = result.state === 'ready'
  const placeholder = ready ? 'Choose a hospital' : result.state === 'failed' ? 'Hospitals couldn’t be loaded' : 'Loading hospitals…'
  return (
    <Field id="hospitalId" label="Base hospital" error={error}>
      <select id="hospitalId" value={value} onChange={(e) => onChange(e.target.value)} disabled={!ready}>
        <option value="">{placeholder}</option>
        {ready &&
          result.data
            .filter((h) => h.isActive)
            .map((h) => (
              <option key={h.id} value={h.id}>
                {h.name}
              </option>
            ))}
      </select>
    </Field>
  )
}
