import { useState, type FormEvent } from 'react'
import { ApiError, fieldErrors } from '../../api/client'
import {
  createOperatingRoom,
  OR_CAPABILITIES,
  OR_STATUSES,
  type OperatingRoom,
  type OperatingRoomInput,
  type OrCapability,
  type OrStatus,
} from '../../api/operatingRooms'
import { Button } from '../../components/form/Button'
import { Field, FieldError } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import styles from '../blood/Blood.module.css'
import hospitalStyles from '../hospitals/Hospitals.module.css'

type FieldName = 'name' | 'capabilities' | 'location' | 'status'
const ORDER: FieldName[] = ['name', 'capabilities', 'location', 'status']
const TARGET: Record<FieldName, string> = {
  name: '#name',
  capabilities: 'input[name="capabilities"]',
  location: '#location',
  status: '#status',
}
const EMPTY: OperatingRoomInput = { name: '', capabilities: [], location: '', status: 'available' }

/** "Register operating room" button that opens into the form (story #28). Admins and nurses only. */
export function RegisterOperatingRoomForm({ onRegistered }: { onRegistered: (room: OperatingRoom) => void }) {
  const [open, setOpen] = useState(false)
  if (!open) {
    return (
      <button type="button" className={styles.more} onClick={() => setOpen(true)}>
        Register operating room
      </button>
    )
  }
  return <OperatingRoomForm onRegistered={onRegistered} onClose={() => setOpen(false)} />
}

function OperatingRoomForm({ onRegistered, onClose }: { onRegistered: (room: OperatingRoom) => void; onClose: () => void }) {
  const [values, setValues] = useState<OperatingRoomInput>(EMPTY)
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)

  const set =
    <K extends keyof OperatingRoomInput>(key: K) =>
    (value: OperatingRoomInput[K]) => {
      setValues((v) => ({ ...v, [key]: value }))
      setErrors((e) => ({ ...e, [key]: undefined }))
    }

  const toggleCapability = (code: OrCapability, on: boolean) =>
    set('capabilities')(on ? [...values.capabilities, code] : values.capabilities.filter((c) => c !== code))

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const found: Partial<Record<FieldName, string>> = {}
    if (!values.name.trim()) found.name = 'Enter a name for the room, e.g. OR 4.'
    if (values.capabilities.length === 0) found.capabilities = 'Pick at least one capability.'
    const focusFirst = (errs: typeof found) => {
      const first = ORDER.find((k) => errs[k])
      if (first) form.querySelector<HTMLElement>(TARGET[first])?.focus()
      return first
    }
    setErrors(found)
    setAlert(undefined)
    if (focusFirst(found)) {
      setAlert('The room wasn’t registered. Fix the fields marked above.')
      return
    }

    setPending(true)
    try {
      onRegistered(await createOperatingRoom({ ...values, name: values.name.trim(), location: values.location.trim() }))
      onClose()
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      const server = fieldErrors(error)
      const onFields: typeof found = {}
      for (const key of ORDER) if (server[key]) onFields[key] = server[key]
      setErrors(onFields)
      if (status === 400 && focusFirst(onFields)) setAlert('The room wasn’t registered. Fix the fields marked above.')
      else if (status === 403) setAlert('Your role can’t register operating rooms.')
      else setAlert('The hospital’s system didn’t respond, so the room wasn’t registered. Try again.')
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title="Register operating room">
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <TextField
          id="name"
          label="Name"
          hint='The name on the door, e.g. "OR 1" or "Cardiac theatre".'
          value={values.name}
          onChange={set('name')}
          error={errors.name}
          autoComplete="off"
        />
        <fieldset className={hospitalStyles.fieldset} aria-describedby={errors.capabilities ? 'capabilities-error' : undefined}>
          <legend>Capabilities</legend>
          <div className={hospitalStyles.options}>
            {OR_CAPABILITIES.map((c) => (
              <label key={c.value} className={hospitalStyles.option}>
                <input
                  type="checkbox"
                  name="capabilities"
                  value={c.value}
                  checked={values.capabilities.includes(c.value)}
                  onChange={(e) => toggleCapability(c.value, e.target.checked)}
                />
                {c.label}
              </label>
            ))}
          </div>
          <FieldError id="capabilities">{errors.capabilities}</FieldError>
        </fieldset>
        <TextField
          id="location"
          label="Location"
          optional
          hint='Where to find it, e.g. "Block B, floor 2".'
          value={values.location}
          onChange={set('location')}
          error={errors.location}
        />
        <Field id="status" label="Status" error={errors.status}>
          <select id="status" value={values.status} onChange={(e) => set('status')(e.target.value as OrStatus)}>
            {OR_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>
        {alert && <FormAlert>{alert}</FormAlert>}
        <div className={styles.formActions}>
          <Button pending={pending} pendingLabel="Registering…">
            Register operating room
          </Button>
          <button type="button" className={styles.more} onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  )
}
