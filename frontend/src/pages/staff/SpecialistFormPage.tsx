import { useCallback, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, fieldErrors } from '../../api/client'
import { getHospitals, type Hospital } from '../../api/hospitals'
import { createSpecialist, getSpecialist, updateSpecialist, type SpecialistDetail } from '../../api/specialists'
import { Button } from '../../components/form/Button'
import { Checkbox } from '../../components/form/Checkbox'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import styles from '../../features/blood/Blood.module.css'
import { AccessDenied } from '../../features/staff/AccessDenied'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'

/** The fields the server can refuse, in the order they appear. */
type FieldKey = 'name' | 'specialty' | 'hospitalId'
const ORDER: FieldKey[] = ['name', 'specialty', 'hospitalId']

/** /staff/specialists/new and /staff/specialists/:id/edit (story #61). Admins and nurses; the API refuses the rest too. */
export default function SpecialistFormPage() {
  const { role } = useStaff()
  const { id } = useParams()
  if (!canEdit(role, 'specialists')) return <AccessDenied what="the specialist editor" />
  return <SpecialistFormLoader key={id ?? 'new'} specialistId={id ? Number(id) : null} />
}

function SpecialistFormLoader({ specialistId }: { specialistId: number | null }) {
  const { result } = useLoad(
    useCallback(
      () => Promise.all([getHospitals(), specialistId === null ? null : getSpecialist(specialistId)]),
      [specialistId],
    ),
  )
  if (result.state === 'failed' && result.status === 404) return <p role="status">No specialist with that id.</p>
  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />
  const [hospitals, specialist] = result.data
  return <SpecialistForm hospitals={hospitals} specialistId={specialistId} specialist={specialist} />
}

type FormValues = { name: string; specialty: string; hospitalId: string; isActive: boolean }
type Errors = Partial<Record<FieldKey, string>>

function SpecialistForm({
  hospitals,
  specialistId,
  specialist,
}: {
  hospitals: Hospital[]
  specialistId: number | null
  specialist: SpecialistDetail | null
}) {
  const navigate = useNavigate()
  const { role, user } = useStaff()
  const editing = specialistId !== null
  // An admin can list a specialist at any active hospital; anyone else only at their own.
  const choices = hospitals.filter((h) => h.isActive && (role === 'admin' || h.id === user.hospital?.id))
  const [values, setValues] = useState<FormValues>({
    name: specialist?.name ?? '',
    specialty: specialist?.specialty ?? '',
    hospitalId: String(specialist?.hospital.id ?? choices[0]?.id ?? ''),
    isActive: specialist?.isActive ?? true,
  })
  const [errors, setErrors] = useState<Errors>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)
  const backTo = editing ? `/staff/specialists/${specialistId}` : '/staff/specialists'

  /** Typing in a text field or choosing a hospital clears that field's error. */
  const setField = (key: FieldKey) => (value: string) => {
    setValues((v) => ({ ...v, [key]: value }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  /** Put the cursor on the first field with an error, as the other staff forms do. */
  const focusFirst = (form: HTMLFormElement, found: Errors) => {
    const first = ORDER.find((key) => found[key])
    if (first) (form.elements.namedItem(first) as HTMLElement | null)?.focus()
    return first
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const found: Errors = {}
    if (!values.name.trim()) found.name = 'Enter the name, e.g. Dr. Ayesha Khan.'
    if (!values.specialty.trim()) found.specialty = 'Enter the specialty, e.g. Cardiology.'
    if (!editing && !values.hospitalId) found.hospitalId = 'Choose a hospital.'
    setErrors(found)
    setAlert(undefined)
    if (focusFirst(form, found)) {
      setAlert('The specialist wasn’t saved. Fix the fields marked above.')
      return
    }

    setPending(true)
    try {
      const name = values.name.trim()
      const specialty = values.specialty.trim()
      const saved =
        specialistId === null
          ? await createSpecialist({ name, specialty, hospitalId: Number(values.hospitalId) })
          : await updateSpecialist(specialistId, { name, specialty, isActive: values.isActive })
      navigate(`/staff/specialists/${saved.id}`)
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      const server = fieldErrors(error)
      const onFields: Errors = {}
      for (const key of ORDER) if (server[key]) onFields[key] = server[key]
      setErrors(onFields)
      if (status === 400 && focusFirst(form, onFields)) {
        setAlert('The specialist wasn’t saved. Fix the fields marked above.')
      } else if (status === 403) {
        setAlert(server.detail ?? 'Your role can’t change specialists.')
      } else {
        setAlert('The hospital’s system didn’t respond, so nothing was saved. Try again.')
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title={editing ? `Edit ${specialist?.name}` : 'Add a specialist'}>
      <form
        className={styles.form}
        onSubmit={handleSubmit}
        noValidate
        aria-label={editing ? 'Edit specialist' : 'Add specialist'}
      >
        <TextField
          id="name"
          label="Name"
          value={values.name}
          onChange={setField('name')}
          error={errors.name}
          autoComplete="off"
        />
        <TextField
          id="specialty"
          label="Specialty"
          hint="Free text, as staff would say it, e.g. Cardiology."
          value={values.specialty}
          onChange={setField('specialty')}
          error={errors.specialty}
          autoComplete="off"
        />
        {editing ? (
          <p>
            Hospital: <strong>{specialist?.hospital.name}</strong>. A specialist stays at the hospital they were listed
            at. To move one, list a new profile and deactivate this one.
          </p>
        ) : (
          <Field
            id="hospitalId"
            label="Hospital"
            error={errors.hospitalId}
            hint={
              choices.length === 0
                ? 'Your account isn’t linked to a hospital, so you can’t list a specialist.'
                : undefined
            }
          >
            <select
              id="hospitalId"
              value={values.hospitalId}
              onChange={(e) => setField('hospitalId')(e.target.value)}
              disabled={choices.length === 0}
            >
              {choices.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
            </select>
          </Field>
        )}
        {editing && (
          <Checkbox
            id="active"
            checked={values.isActive}
            onChange={(checked) => setValues((v) => ({ ...v, isActive: checked }))}
          >
            Active: on the list, and can be on call
          </Checkbox>
        )}
        {alert && <FormAlert>{alert}</FormAlert>}
        <div className={styles.formActions}>
          <Button pending={pending} pendingLabel="Saving…">
            {editing ? 'Save changes' : 'Add specialist'}
          </Button>
          <Link to={backTo} className={styles.more}>
            Cancel
          </Link>
        </div>
      </form>
    </Panel>
  )
}
