import { useState } from 'react'
import {
  AMBULANCE_STATUSES,
  AMBULANCE_TYPES,
  getAmbulances,
  postAmbulanceAction,
  type Ambulance,
  type AmbulanceAction,
  type AmbulanceStatus,
  type AmbulanceType,
} from '../../api/ambulances'
import { ApiError } from '../../api/client'
import { TRIP_STATUS_LABEL } from '../../api/trips'
import { FormAlert } from '../../components/form/FormAlert'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge, type Tone } from '../../components/ui/StatusBadge'
import bedStyles from '../../features/beds/Beds.module.css'
import { actionsFor } from '../../features/ambulances/ambulances'
import { RegisterAmbulanceForm } from '../../features/ambulances/RegisterAmbulanceForm'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

type TypeFilter = 'all' | AmbulanceType
type StatusFilter = 'all' | AmbulanceStatus

const TONE: Record<AmbulanceStatus, Tone> = {
  available: 'ok',
  dispatched: 'neutral',
  maintenance: 'warning',
  outOfService: 'critical',
}
const statusLabel = (s: AmbulanceStatus) => AMBULANCE_STATUSES.find((x) => x.value === s)!.label
const typeLabel = (t: AmbulanceType) => AMBULANCE_TYPES.find((x) => x.value === t)!.label

/** Ambulance registry (story #50): every ambulance with its base hospital, type and status. */
export default function AmbulancesPage() {
  const { role } = useStaff()
  const { result, setData } = useLoad(getAmbulances)
  const [type, setType] = useState<TypeFilter>('all')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [busyId, setBusyId] = useState<number>()
  const [announcement, setAnnouncement] = useState('')
  const [error, setError] = useState<string>()

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const items = result.data
  const editable = canEdit(role, 'ambulances')
  const shown = items.filter((a) => (type === 'all' || a.type === type) && (status === 'all' || a.status === status))
  const typeOptions = [{ value: 'all' as const, label: 'All' }, ...AMBULANCE_TYPES].map((o) => ({
    ...o,
    count: items.filter((a) => o.value === 'all' || a.type === o.value).length,
  }))
  const statusOptions = [{ value: 'all' as const, label: 'Any status' }, ...AMBULANCE_STATUSES].map((o) => ({
    ...o,
    count: items.filter((a) => (type === 'all' || a.type === type) && (o.value === 'all' || a.status === o.value)).length,
  }))
  const available = items.filter((a) => a.status === 'available').length

  /** Save the move, update the row from the server's copy, then announce it. */
  const change = async (item: Ambulance, action: AmbulanceAction) => {
    setBusyId(item.id)
    setError(undefined)
    try {
      const saved = await postAmbulanceAction(item.id, action)
      setData((current) => current.map((a) => (a.id === saved.id ? saved : a)))
      setAnnouncement(`${item.identifier} is now ${statusLabel(saved.status).toLowerCase()}`)
    } catch (err) {
      setError(`${item.identifier}: ${await failureMessage(err, setData)}`)
    } finally {
      setBusyId(undefined)
    }
  }

  return (
    <div className={pageStyles.stack}>
      {editable && <RegisterAmbulanceForm onRegistered={(item) => setData((current) => [...current, item])} />}
      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {announcement}
      </p>
      <Panel title="Ambulances">
        <p>
          {available} of {items.length} available right now.
        </p>
        <div className={pageStyles.toolbar}>
          <FilterBar label="Show ambulance type" options={typeOptions} value={type} onChange={setType} />
          <FilterBar label="Show status" options={statusOptions} value={status} onChange={setStatus} />
        </div>
        {items.length === 0 ? (
          <p>No ambulances registered yet.</p>
        ) : shown.length === 0 ? (
          <p>No ambulances match. Choose another type or status.</p>
        ) : (
          <div className="table-scroll">
            <table aria-label="Ambulances">
              <thead>
                <tr>
                  <th scope="col">Asset tag</th>
                  <th scope="col">Type</th>
                  <th scope="col">Base hospital</th>
                  <th scope="col">Status</th>
                  {editable && <th scope="col">Change status</th>}
                </tr>
              </thead>
              <tbody>
                {shown.map((a: Ambulance) => (
                  <tr key={a.id}>
                    <th scope="row">{a.identifier}</th>
                    <td>{typeLabel(a.type)}</td>
                    <td>{a.hospital ?? '—'}</td>
                    <td>
                      <StatusBadge tone={TONE[a.status]}>{statusLabel(a.status)}</StatusBadge>
                      {a.trip && (
                        <p className={pageStyles.hint}>
                          Carrying transfer #{a.trip.transferId}, {TRIP_STATUS_LABEL[a.trip.status].toLowerCase()}
                        </p>
                      )}
                    </td>
                    {editable && (
                      <td>
                        <div className={bedStyles.actions}>
                          {actionsFor(a.status).map((t) => (
                            <button
                              key={t.action}
                              type="button"
                              className={bedStyles.action}
                              aria-label={`${t.label} ${a.identifier}`}
                              disabled={busyId === a.id}
                              onClick={() => change(a, t.action)}
                            >
                              {t.label}
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

const NO_RESPONSE = 'The hospital’s system didn’t respond, so the status wasn’t changed. Try again.'

/** Why a move failed. A 409 means someone moved the ambulance first, so the list is reloaded. */
async function failureMessage(error: unknown, setData: (update: (current: Ambulance[]) => Ambulance[]) => void): Promise<string> {
  if (!(error instanceof ApiError)) return NO_RESPONSE
  if (error.status === 403) return 'Your role can’t change ambulances.'
  if (error.status === 409) {
    const fresh = await getAmbulances().catch(() => null)
    if (fresh) setData(() => fresh)
    return 'That move is no longer allowed, because the status changed first. The list shows the latest status.'
  }
  return NO_RESPONSE
}
