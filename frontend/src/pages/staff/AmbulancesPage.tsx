import { useState, type FormEvent } from 'react'
import {
  AMBULANCE_MOVES,
  AMBULANCE_STATUSES,
  AMBULANCE_TYPES,
  getAmbulances,
  postAmbulanceAction,
  registerAmbulance,
  type Ambulance,
  type AmbulanceAction,
  type AmbulanceStatus,
  type AmbulanceType,
} from '../../api/ambulances'
import { ApiError, fieldErrors } from '../../api/client'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge, type Tone } from '../../components/ui/StatusBadge'
import bedStyles from '../../features/beds/Beds.module.css'
import formStyles from '../../features/blood/Blood.module.css'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

const TONE: Record<AmbulanceStatus, Tone> = { available: 'ok', onTrip: 'neutral', maintenance: 'warning', outOfService: 'critical' }
const statusLabel = (s: AmbulanceStatus) => AMBULANCE_STATUSES.find((x) => x.value === s)!.label
const typeLabel = (t: AmbulanceType) => AMBULANCE_TYPES.find((x) => x.value === t)!.label

/** Ambulance registry (story #50): the fleet, its status, and registering a vehicle. */
export default function AmbulancesPage() {
  const { role } = useStaff()
  const { result, setData } = useLoad(getAmbulances)
  const [status, setStatus] = useState<'all' | AmbulanceStatus>('all')
  const [busyId, setBusyId] = useState<number>()
  const [error, setError] = useState<string>()

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const items = result.data
  const editable = canEdit(role, 'ambulances')
  const shown = items.filter((a) => status === 'all' || a.status === status)
  const options = [{ value: 'all' as const, label: 'Any status' }, ...AMBULANCE_STATUSES].map((o) => ({
    ...o,
    count: items.filter((a) => o.value === 'all' || a.status === o.value).length,
  }))

  const change = async (item: Ambulance, action: AmbulanceAction) => {
    setBusyId(item.id)
    setError(undefined)
    try {
      const saved = await postAmbulanceAction(item.id, action)
      setData((current) => current.map((a) => (a.id === saved.id ? saved : a)))
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 409
          ? `${item.identifier}: that move is no longer allowed. Reload to see its latest status.`
          : `${item.identifier}: the status wasn’t changed. Try again.`,
      )
    } finally {
      setBusyId(undefined)
    }
  }

  return (
    <div className={pageStyles.stack}>
      {editable && <RegisterAmbulance onRegistered={(a) => setData((current) => [...current, a])} />}
      <FormAlert>{error}</FormAlert>
      <Panel title="Fleet">
        <p>
          {items.filter((a) => a.status === 'available').length} of {items.length} ready to dispatch.
        </p>
        <div className={pageStyles.toolbar}>
          <FilterBar label="Show status" options={options} value={status} onChange={setStatus} />
        </div>
        {shown.length === 0 ? (
          <p>No ambulances match.</p>
        ) : (
          <div className="table-scroll">
            <table aria-label="Ambulances">
              <thead>
                <tr>
                  <th scope="col">Fleet number</th>
                  <th scope="col">Type</th>
                  <th scope="col">Plate</th>
                  <th scope="col">Base</th>
                  <th scope="col">Status</th>
                  {editable && <th scope="col">Change status</th>}
                </tr>
              </thead>
              <tbody>
                {shown.map((a) => (
                  <tr key={a.id}>
                    <th scope="row">{a.identifier}</th>
                    <td>{typeLabel(a.type)}</td>
                    <td>{a.plate || '—'}</td>
                    <td>{a.hospital}</td>
                    <td>
                      <StatusBadge tone={TONE[a.status]}>{statusLabel(a.status)}</StatusBadge>
                    </td>
                    {editable && (
                      <td>
                        <div className={bedStyles.actions}>
                          {AMBULANCE_MOVES[a.status].map((m) => (
                            <button
                              key={m.action}
                              type="button"
                              className={bedStyles.action}
                              aria-label={`${m.label} ${a.identifier}`}
                              disabled={busyId === a.id}
                              onClick={() => change(a, m.action)}
                            >
                              {m.label}
                            </button>
                          ))}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}

function RegisterAmbulance({ onRegistered }: { onRegistered: (a: Ambulance) => void }) {
  const [open, setOpen] = useState(false)
  const [identifier, setIdentifier] = useState('')
  const [type, setType] = useState<AmbulanceType>('als')
  const [plate, setPlate] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)

  if (!open) {
    return (
      <button type="button" className={formStyles.more} onClick={() => setOpen(true)}>
        Register ambulance
      </button>
    )
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!identifier.trim()) return setErrors({ identifier: 'Enter the fleet number, e.g. AMB-CG-04.' })
    setPending(true)
    try {
      onRegistered(await registerAmbulance({ identifier: identifier.trim(), type, plate: plate.trim() }))
      setOpen(false)
      setIdentifier('')
      setPlate('')
      setErrors({})
    } catch (error) {
      const found = fieldErrors(error)
      setErrors(Object.keys(found).length ? found : { detail: 'The ambulance wasn’t registered. Try again.' })
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title="Register ambulance">
      <form className={formStyles.form} onSubmit={submit} noValidate>
        <TextField id="identifier" label="Fleet number" value={identifier} onChange={setIdentifier} error={errors.identifier} />
        <Field id="ambulance-type" label="Type">
          <select id="ambulance-type" value={type} onChange={(e) => setType(e.target.value as AmbulanceType)}>
            {AMBULANCE_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </Field>
        <TextField id="plate" label="Plate" optional value={plate} onChange={setPlate} error={errors.plate} />
        <FormAlert>{errors.detail}</FormAlert>
        <div className={formStyles.formActions}>
          <Button pending={pending} pendingLabel="Registering…">
            Register ambulance
          </Button>
          <button type="button" className={formStyles.more} onClick={() => setOpen(false)}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  )
}
