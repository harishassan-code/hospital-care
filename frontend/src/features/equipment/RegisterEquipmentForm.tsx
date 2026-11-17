import { useState, type FormEvent } from 'react'
import { ApiError, fieldErrors } from '../../api/client'
import {
  createEquipment,
  EQUIPMENT_STATUSES,
  EQUIPMENT_TYPES,
  type Equipment,
  type EquipmentInput,
} from '../../api/equipment'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import styles from '../blood/Blood.module.css'

type FieldName = 'identifier' | 'type' | 'name' | 'location' | 'status'
const ORDER: FieldName[] = ['identifier', 'type', 'name', 'location', 'status']
const EMPTY: EquipmentInput = { identifier: '', type: 'ventilator', name: '', location: '', status: 'available' }

/** "Register equipment" button that opens into the form (story #26). Admins and nurses only. */
export function RegisterEquipmentForm({ onRegistered }: { onRegistered: (item: Equipment) => void }) {
  const [open, setOpen] = useState(false)
  if (!open) {
    return (
      <button type="button" className={styles.more} onClick={() => setOpen(true)}>
        Register equipment
      </button>
    )
  }
  return <EquipmentForm onRegistered={onRegistered} onClose={() => setOpen(false)} />
}

function EquipmentForm({ onRegistered, onClose }: { onRegistered: (item: Equipment) => void; onClose: () => void }) {
  const [values, setValues] = useState<EquipmentInput>(EMPTY)
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
    if (!values.identifier.trim()) found.identifier = 'Enter the asset tag, e.g. VENT-006.'
    if (!values.location.trim()) found.location = 'Say where the equipment is kept.'
    const focusFirst = (errs: typeof found) => {
      const first = ORDER.find((k) => errs[k])
      if (first) (form.elements.namedItem(first) as HTMLElement | null)?.focus()
      return first
    }
    setErrors(found)
    setAlert(undefined)
    if (focusFirst(found)) {
      setAlert('The equipment wasn’t registered. Fix the fields marked above.')
      return
    }

    setPending(true)
    try {
      onRegistered(await createEquipment({ ...values, identifier: values.identifier.trim(), location: values.location.trim() }))
      onClose()
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      const server = fieldErrors(error)
      const onFields: typeof found = {}
      for (const key of ORDER) if (server[key]) onFields[key] = server[key]
      setErrors(onFields)
      if (status === 400 && focusFirst(onFields)) setAlert('The equipment wasn’t registered. Fix the fields marked above.')
      else if (status === 403) setAlert('Your role can’t register equipment.')
      else setAlert('The hospital’s system didn’t respond, so the equipment wasn’t registered. Try again.')
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title="Register equipment">
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <TextField
          id="identifier"
          label="Asset tag"
          hint="The label on the device, e.g. VENT-006."
          value={values.identifier}
          onChange={set('identifier')}
          error={errors.identifier}
          autoComplete="off"
        />
        <div className={styles.pair}>
          <Field id="type" label="Type" error={errors.type}>
            <select id="type" value={values.type} onChange={(e) => set('type')(e.target.value)}>
              {EQUIPMENT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label.replace(/s$/, '')}
                </option>
              ))}
            </select>
          </Field>
          <Field id="status" label="Status" error={errors.status}>
            <select id="status" value={values.status} onChange={(e) => set('status')(e.target.value)}>
              {EQUIPMENT_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <TextField id="name" label="Make and model" optional value={values.name} onChange={set('name')} error={errors.name} />
        <TextField
          id="location"
          label="Location"
          hint="Where to find it, e.g. ICU bay 2."
          value={values.location}
          onChange={set('location')}
          error={errors.location}
        />
        {alert && <FormAlert>{alert}</FormAlert>}
        <div className={styles.formActions}>
          <Button pending={pending} pendingLabel="Registering…">
            Register equipment
          </Button>
          <button type="button" className={styles.more} onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  )
}
