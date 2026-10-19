import { useCallback, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, fieldErrors } from '../../api/client'
import {
  createHospital,
  getCapabilities,
  getHospital,
  HOSPITAL_TYPES,
  updateHospital,
  type Capability,
  type HospitalType,
} from '../../api/hospitals'
import { Button } from '../../components/form/Button'
import { Checkbox } from '../../components/form/Checkbox'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import type { FieldErrors } from '../../features/auth/validation'
import { firstErrorKey } from '../../features/auth/validation'
import styles from '../../features/hospitals/Hospitals.module.css'
import {
  EMPTY_HOSPITAL,
  HOSPITAL_FIELD_ORDER,
  toFormValues,
  toHospitalInput,
  validateHospital,
  type HospitalField,
  type HospitalFormValues,
} from '../../features/hospitals/validation'
import { AccessDenied } from '../../features/staff/AccessDenied'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'

/** /staff/hospitals/new and /staff/hospitals/:id/edit. Admins only; the API refuses everyone else too. */
export default function HospitalFormPage() {
  const { role } = useStaff()
  const { id } = useParams()
  if (!canEdit(role, 'hospitals')) return <AccessDenied what="the hospital editor" />
  return <HospitalFormLoader key={id ?? 'new'} hospitalId={id ? Number(id) : null} />
}

function HospitalFormLoader({ hospitalId }: { hospitalId: number | null }) {
  const { result } = useLoad(
    useCallback(() => Promise.all([getCapabilities(), hospitalId === null ? null : getHospital(hospitalId)]), [hospitalId]),
  )
  if (result.state === 'failed' && result.status === 404) return <p role="status">No hospital with that id.</p>
  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />
  const [capabilities, hospital] = result.data
  return (
    <HospitalForm
      capabilities={capabilities}
      hospitalId={hospitalId}
      initial={hospital ? toFormValues(hospital) : EMPTY_HOSPITAL}
      title={hospital ? `Edit ${hospital.name}` : 'Register a hospital'}
    />
  )
}

type HospitalFormProps = {
  capabilities: Capability[]
  hospitalId: number | null
  initial: HospitalFormValues
  title: string
}

function HospitalForm({ capabilities, hospitalId, initial, title }: HospitalFormProps) {
  const navigate = useNavigate()
  const [values, setValues] = useState(initial)
  const [errors, setErrors] = useState<FieldErrors<HospitalField>>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)
  const editing = hospitalId !== null
  const backTo = editing ? `/staff/hospitals/${hospitalId}` : '/staff/hospitals'

  const set =
    <K extends HospitalField>(key: K) =>
    (value: HospitalFormValues[K]) => {
      setValues((v) => ({ ...v, [key]: value }))
      setErrors((e) => ({ ...e, [key]: undefined }))
    }

  const toggleCapability = (code: string, on: boolean) =>
    set('capabilities')(on ? [...values.capabilities, code] : values.capabilities.filter((c) => c !== code))

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const focusFirst = (found: FieldErrors<HospitalField>) => {
      const first = firstErrorKey(found, HOSPITAL_FIELD_ORDER)
      if (first) (form.elements.namedItem(first) as HTMLElement | null)?.focus()
      return first
    }
    setAlert(undefined)
    const found = validateHospital(values)
    setErrors(found)
    if (focusFirst(found)) {
      const count = Object.values(found).filter(Boolean).length
      setAlert(`The hospital wasn’t saved. Fix the ${count === 1 ? 'field' : `${count} fields`} marked above.`)
      return
    }

    setPending(true)
    try {
      const input = toHospitalInput(values)
      const saved = editing ? await updateHospital(hospitalId, input) : await createHospital(input)
      navigate(`/staff/hospitals/${saved.id}`)
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      const server = fieldErrors(error)
      const onFields: FieldErrors<HospitalField> = {}
      for (const key of HOSPITAL_FIELD_ORDER) if (server[key]) onFields[key] = server[key]
      setErrors(onFields)
      if (status === 400 && focusFirst(onFields)) {
        setAlert('The hospital wasn’t saved. Fix the fields marked above.')
      } else if (status === 403) {
        setAlert('Your role can’t register or change hospitals.')
      } else {
        setAlert(
          status === 400 && (server.detail || server.capabilities)
            ? (server.detail ?? server.capabilities)
            : 'The hospital’s system didn’t respond, so nothing was saved. Try again.',
        )
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title={title}>
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <TextField id="name" label="Name" value={values.name} onChange={set('name')} error={errors.name} autoComplete="organization" />
        <fieldset className={styles.fieldset}>
          <legend>Type</legend>
          <div className={styles.options}>
            {HOSPITAL_TYPES.map((t) => (
              <label key={t.value} className={styles.option}>
                <input
                  type="radio"
                  name="type"
                  value={t.value}
                  checked={values.type === t.value}
                  onChange={() => set('type')(t.value as HospitalType)}
                />
                {t.label}
              </label>
            ))}
          </div>
        </fieldset>
        <TextField
          id="address"
          label="Address"
          value={values.address}
          onChange={set('address')}
          error={errors.address}
          autoComplete="street-address"
        />
        <div className={styles.pair}>
          <TextField
            id="latitude"
            label="Latitude"
            hint="Decimal degrees, e.g. 24.8607"
            inputMode="decimal"
            value={values.latitude}
            onChange={set('latitude')}
            error={errors.latitude}
          />
          <TextField
            id="longitude"
            label="Longitude"
            hint="Decimal degrees, e.g. 67.0011"
            inputMode="decimal"
            value={values.longitude}
            onChange={set('longitude')}
            error={errors.longitude}
          />
        </div>
        <TextField
          id="phone"
          label="Phone"
          optional
          type="tel"
          value={values.phone}
          onChange={set('phone')}
          error={errors.phone}
          autoComplete="tel"
        />
        <fieldset className={styles.fieldset}>
          <legend>Capabilities</legend>
          {capabilities.length === 0 ? (
            <p>No capabilities are set up yet. An administrator adds them in Django admin.</p>
          ) : (
            <div className={styles.options}>
              {capabilities.map((c) => (
                <label key={c.code} className={styles.option}>
                  <input
                    type="checkbox"
                    checked={values.capabilities.includes(c.code)}
                    onChange={(e) => toggleCapability(c.code, e.target.checked)}
                  />
                  {c.name}
                </label>
              ))}
            </div>
          )}
        </fieldset>
        {editing && (
          <Checkbox id="isActive" checked={values.isActive} onChange={set('isActive')}>
            Active: this hospital takes part in the network. Deactivated hospitals are kept but never offered for matching.
          </Checkbox>
        )}
        <FormAlert>{alert}</FormAlert>
        <div className={styles.formActions}>
          <Button pending={pending} pendingLabel="Saving…">
            Save hospital
          </Button>
          <Link to={backTo} className={styles.back}>
            Cancel
          </Link>
        </div>
      </form>
    </Panel>
  )
}
