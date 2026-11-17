import { useState } from 'react'
import { ApiError } from '../../api/client'
import {
  EQUIPMENT_STATUSES,
  EQUIPMENT_TYPES,
  getEquipment,
  postEquipmentAction,
  type Equipment,
  type EquipmentAction,
  type EquipmentStatus,
  type EquipmentType,
} from '../../api/equipment'
import { FormAlert } from '../../components/form/FormAlert'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge, type Tone } from '../../components/ui/StatusBadge'
import bedStyles from '../../features/beds/Beds.module.css'
import { RegisterEquipmentForm } from '../../features/equipment/RegisterEquipmentForm'
import { actionsFor } from '../../features/equipment/equipment'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

type TypeFilter = 'all' | EquipmentType
type StatusFilter = 'all' | EquipmentStatus

const TONE: Record<EquipmentStatus, Tone> = {
  available: 'ok',
  reserved: 'neutral',
  inUse: 'neutral',
  maintenance: 'warning',
  outOfService: 'critical',
}
const statusLabel = (s: EquipmentStatus) => EQUIPMENT_STATUSES.find((x) => x.value === s)!.label
const typeLabel = (t: EquipmentType) => EQUIPMENT_TYPES.find((x) => x.value === t)!.label.replace(/s$/, '')

/** Equipment registry (story #26) and operational status (story #27). */
export default function EquipmentPage() {
  const { role } = useStaff()
  const { result, setData } = useLoad(getEquipment)
  const [type, setType] = useState<TypeFilter>('all')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [busyId, setBusyId] = useState<number>()
  const [announcement, setAnnouncement] = useState('')
  const [error, setError] = useState<string>()

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const items = result.data
  const editable = canEdit(role, 'equipment')
  const shown = items.filter((e) => (type === 'all' || e.type === type) && (status === 'all' || e.status === status))
  const typeOptions = [{ value: 'all' as const, label: 'All' }, ...EQUIPMENT_TYPES].map((o) => ({
    ...o,
    count: items.filter((e) => o.value === 'all' || e.type === o.value).length,
  }))
  const statusOptions = [{ value: 'all' as const, label: 'Any status' }, ...EQUIPMENT_STATUSES].map((o) => ({
    ...o,
    count: items.filter((e) => (type === 'all' || e.type === type) && (o.value === 'all' || e.status === o.value)).length,
  }))
  const available = items.filter((e) => e.status === 'available').length

  /** Save the change, update the row from the server's copy, then announce it. */
  const change = async (item: Equipment, action: EquipmentAction) => {
    setBusyId(item.id)
    setError(undefined)
    try {
      const saved = await postEquipmentAction(item.id, action)
      setData((current) => current.map((e) => (e.id === saved.id ? saved : e)))
      setAnnouncement(`${item.identifier} is now ${statusLabel(saved.status).toLowerCase()}`)
    } catch (err) {
      setError(`${item.identifier}: ${await failureMessage(err, setData)}`)
    } finally {
      setBusyId(undefined)
    }
  }

  return (
    <div className={pageStyles.stack}>
      {editable && (
        <RegisterEquipmentForm onRegistered={(item) => setData((current) => [...current, item])} />
      )}
      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {announcement}
      </p>
      <Panel title="Critical equipment">
        <p>
          {available} of {items.length} available right now.
        </p>
        <div className={pageStyles.toolbar}>
          <FilterBar label="Show equipment type" options={typeOptions} value={type} onChange={setType} />
          <FilterBar label="Show status" options={statusOptions} value={status} onChange={setStatus} />
        </div>
        {items.length === 0 ? (
          <p>No equipment registered yet.</p>
        ) : shown.length === 0 ? (
          <p>No equipment matches. Choose another type or status.</p>
        ) : (
          <div className="table-scroll">
            <table aria-label="Equipment">
              <thead>
                <tr>
                  <th scope="col">Asset tag</th>
                  <th scope="col">Type</th>
                  <th scope="col">Make and model</th>
                  <th scope="col">Location</th>
                  <th scope="col">Status</th>
                  {editable && <th scope="col">Change status</th>}
                </tr>
              </thead>
              <tbody>
                {shown.map((e: Equipment) => (
                  <tr key={e.id}>
                    <th scope="row">{e.identifier}</th>
                    <td>{typeLabel(e.type)}</td>
                    <td>{e.name || '—'}</td>
                    <td>{e.location}</td>
                    <td>
                      <StatusBadge tone={TONE[e.status]}>{statusLabel(e.status)}</StatusBadge>
                    </td>
                    {editable && (
                      <td>
                        <div className={bedStyles.actions}>
                          {actionsFor(e.status).map((t) => (
                            <button
                              key={t.action}
                              type="button"
                              className={bedStyles.action}
                              aria-label={`${t.label} ${e.identifier}`}
                              disabled={busyId === e.id}
                              onClick={() => change(e, t.action)}
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

/** Why a status change failed. A 409 means someone moved the item first, so the list is reloaded. */
async function failureMessage(error: unknown, setData: (update: (current: Equipment[]) => Equipment[]) => void): Promise<string> {
  if (!(error instanceof ApiError)) return NO_RESPONSE
  if (error.status === 403) return 'Your role can’t change equipment status.'
  if (error.status === 409) {
    const fresh = await getEquipment().catch(() => null)
    if (fresh) setData(() => fresh)
    return 'That move is no longer allowed, because the status changed first. The list shows the latest status.'
  }
  return NO_RESPONSE
}
