import { useState, type FormEvent } from 'react'
import { BLOOD_GROUPS, COMPONENTS, createBloodUnit, type BloodUnit } from '../../api/blood'
import { ApiError, fieldErrors } from '../../api/client'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { firstErrorKey, type FieldErrors } from '../auth/validation'
import { COMPONENT_LABEL, formatGroup } from './blood'
import styles from './Blood.module.css'
import { emptyUnit, UNIT_FIELD_ORDER, toUnitInput, validateUnit, withComponent, type UnitField, type UnitFormValues } from './validation'

type Props = {
  now: Date
  onRegistered: (unit: BloodUnit) => void
}

/** Collapsed "Register a unit" button that opens into the form (story #17). Blood-bank and admin only. */
export function RegisterUnitForm({ now, onRegistered }: Props) {
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <button type="button" className={styles.more} onClick={() => setOpen(true)}>
        Register a unit
      </button>
    )
  }

  return <UnitForm now={now} onRegistered={onRegistered} onClose={() => setOpen(false)} />
}

function UnitForm({ now, onRegistered, onClose }: Props & { onClose: () => void }) {
  const [values, setValues] = useState<UnitFormValues>(() => emptyUnit(now))
  const [errors, setErrors] = useState<FieldErrors<UnitField>>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)

  const component = COMPONENTS.find((c) => c.id === values.component)!

  const set =
    <K extends UnitField>(key: K) =>
    (value: UnitFormValues[K]) => {
      setValues((v) => (key === 'component' ? withComponent(v, value as (typeof COMPONENTS)[number]['id']) : { ...v, [key]: value }))
      setErrors((e) => ({ ...e, [key]: undefined }))
    }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const focusFirst = (found: FieldErrors<UnitField>) => {
      const first = firstErrorKey(found, UNIT_FIELD_ORDER)
      if (first) (form.elements.namedItem(first) as HTMLElement | null)?.focus()
      return first
    }
    setAlert(undefined)
    const found = validateUnit(values, now)
    setErrors(found)
    if (focusFirst(found)) {
      setAlert('The unit wasn’t registered. Fix the fields marked above.')
      return
    }

    setPending(true)
    try {
      const created = await createBloodUnit(toUnitInput(values))
      onRegistered(created)
      onClose()
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      const server = fieldErrors(error)
      const onFields: FieldErrors<UnitField> = {}
      for (const key of UNIT_FIELD_ORDER) if (server[key]) onFields[key] = server[key]
      setErrors(onFields)
      if (status === 400 && focusFirst(onFields)) {
        setAlert('The unit wasn’t registered. Fix the fields marked above.')
      } else if (status === 403) {
        setAlert('Your role can’t register blood units.')
      } else {
        setAlert('The hospital’s system didn’t respond, so the unit wasn’t registered. Try again.')
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title="Register a unit">
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <TextField
          id="id"
          label="Unit ID"
          hint="The donation number, e.g. ISBT 128."
          value={values.id}
          onChange={set('id')}
          error={errors.id}
          autoComplete="off"
        />
        <div className={styles.pair}>
          <Field id="group" label="Blood group">
            <select id="group" value={values.group} onChange={(e) => set('group')(e.target.value as UnitFormValues['group'])}>
              {BLOOD_GROUPS.map((g) => (
                <option key={g} value={g}>
                  {formatGroup(g)}
                </option>
              ))}
            </select>
          </Field>
          <Field id="component" label="Component">
            <select id="component" value={values.component} onChange={(e) => set('component')(e.target.value as UnitFormValues['component'])}>
              {COMPONENTS.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <TextField id="collectedAt" label="Collected on" type="date" value={values.collectedAt} onChange={set('collectedAt')} error={errors.collectedAt} />
        <Field id="location" label="Storage location" error={errors.location}>
          <select id="location" value={values.location} onChange={(e) => set('location')(e.target.value)}>
            {component.location.map((loc) => (
              <option key={loc} value={loc}>
                {loc}
              </option>
            ))}
          </select>
        </Field>
        <p className={styles.note}>
          Expires {component.shelfLifeDays} days after collection, the usual shelf life for {COMPONENT_LABEL[component.id].toLowerCase()} — the lab can
          set a different date once testing is done.
        </p>
        <FormAlert>{alert}</FormAlert>
        <div className={styles.formActions}>
          <Button pending={pending} pendingLabel="Registering…">
            Register unit
          </Button>
          <button type="button" className={styles.back} onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  )
}
