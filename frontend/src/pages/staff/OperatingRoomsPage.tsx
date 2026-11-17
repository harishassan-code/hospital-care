import { useCallback, useState } from 'react'
import { ApiError } from '../../api/client'
import {
  getOperatingRooms,
  OR_CAPABILITIES,
  OR_STATUSES,
  postOperatingRoomAction,
  type OperatingRoom,
  type OperatingRoomAction,
  type OperatingRoomFilters,
  type OrCapability,
  type OrStatus,
} from '../../api/operatingRooms'
import { FormAlert } from '../../components/form/FormAlert'
import { ButtonLink } from '../../components/form/Button'
import { FilterBar, type FilterOption } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import bedStyles from '../../features/beds/Beds.module.css'
import hospitalStyles from '../../features/hospitals/Hospitals.module.css'
import { actionsFor, ROOM_TONE } from '../../features/operatingRooms/operatingRooms'
import { RegisterOperatingRoomForm } from '../../features/operatingRooms/RegisterOperatingRoomForm'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

type CapabilityFilter = 'all' | OrCapability
type StatusFilter = 'all' | OrStatus

const statusLabel = (s: OrStatus) => OR_STATUSES.find((x) => x.value === s)!.label
const capabilityLabel = (c: OrCapability) => OR_CAPABILITIES.find((x) => x.value === c)!.label
const capabilityOptions: readonly FilterOption<CapabilityFilter>[] = [{ value: 'all', label: 'All' }, ...OR_CAPABILITIES]
const statusOptions: readonly FilterOption<StatusFilter>[] = [{ value: 'all', label: 'Any status' }, ...OR_STATUSES]

/** "all" means no filter; the API takes the codes only. */
function filtersFrom(capability: CapabilityFilter, status: StatusFilter): OperatingRoomFilters {
  return {
    capability: capability === 'all' ? undefined : capability,
    status: status === 'all' ? undefined : status,
  }
}

/** Operating room registry (story #28): filter by capability and status, register, and change status. */
export default function OperatingRoomsPage() {
  const { role } = useStaff()
  const [capability, setCapability] = useState<CapabilityFilter>('all')
  const [status, setStatus] = useState<StatusFilter>('all')
  // Filters are applied by the server, so the page loads again whenever one changes.
  const load = useCallback(() => getOperatingRooms(filtersFrom(capability, status)), [capability, status])
  const { result, setData } = useLoad(load)
  const [busyId, setBusyId] = useState<number>()
  const [announcement, setAnnouncement] = useState('')
  const [error, setError] = useState<string>()

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const rooms = result.data
  const editable = canEdit(role, 'operatingRooms')
  const filtered = capability !== 'all' || status !== 'all'
  const matchesFilters = (room: OperatingRoom) =>
    (capability === 'all' || room.capabilities.includes(capability)) && (status === 'all' || room.status === status)

  /** Reload with the current filters, after a 409 showed the list is out of date. */
  const reload = async () => {
    const fresh = await getOperatingRooms(filtersFrom(capability, status)).catch(() => null)
    if (fresh) setData(() => fresh)
  }

  /** Save the change, update the row from the server's copy, then announce it. */
  const change = async (room: OperatingRoom, action: OperatingRoomAction) => {
    setBusyId(room.id)
    setError(undefined)
    try {
      const saved = await postOperatingRoomAction(room.id, action)
      setData((current) => current.map((r) => (r.id === saved.id ? saved : r)))
      setAnnouncement(`${room.name} is now ${statusLabel(saved.status).toLowerCase()}`)
    } catch (err) {
      setError(`${room.name}: ${await failureMessage(err, reload)}`)
    } finally {
      setBusyId(undefined)
    }
  }

  return (
    <div className={pageStyles.stack}>
      {editable && (
        <RegisterOperatingRoomForm
          onRegistered={(room) => {
            if (matchesFilters(room)) setData((current) => [...current, room])
          }}
        />
      )}
      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {announcement}
      </p>
      <Panel
        title="Operating rooms"
        aside={
          <ButtonLink to="/staff/operating-rooms/schedule" variant="secondary">
            Day schedule
          </ButtonLink>
        }
      >
        <div className={pageStyles.toolbar}>
          <FilterBar label="Show capability" options={capabilityOptions} value={capability} onChange={setCapability} />
          <FilterBar label="Show status" options={statusOptions} value={status} onChange={setStatus} />
        </div>
        {rooms.length === 0 ? (
          <p>{filtered ? 'No operating rooms match. Choose another capability or status.' : 'No operating rooms registered yet.'}</p>
        ) : (
          <div className="table-scroll">
            <table aria-label="Operating rooms">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Capabilities</th>
                  <th scope="col">Location</th>
                  <th scope="col">Status</th>
                  {editable && <th scope="col">Change status</th>}
                </tr>
              </thead>
              <tbody>
                {rooms.map((room) => (
                  <tr key={room.id}>
                    <th scope="row">{room.name}</th>
                    <td>
                      <ul className={hospitalStyles.chips} aria-label={`Capabilities of ${room.name}`}>
                        {room.capabilities.map((c) => (
                          <li key={c}>{capabilityLabel(c)}</li>
                        ))}
                      </ul>
                    </td>
                    <td>{room.location || '—'}</td>
                    <td>
                      <StatusBadge tone={ROOM_TONE[room.status]}>{statusLabel(room.status)}</StatusBadge>
                    </td>
                    {editable && (
                      <td>
                        <div className={bedStyles.actions}>
                          {actionsFor(room.status).map((t) => (
                            <button
                              key={t.action}
                              type="button"
                              className={bedStyles.action}
                              aria-label={`${t.label} ${room.name}`}
                              disabled={busyId === room.id}
                              onClick={() => change(room, t.action)}
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

/** Why a status change failed. A 409 means someone moved the room first, so the list is reloaded. */
async function failureMessage(error: unknown, reload: () => Promise<void>): Promise<string> {
  if (!(error instanceof ApiError)) return NO_RESPONSE
  if (error.status === 403) return 'Your role can’t change operating room status.'
  if (error.status === 409) {
    await reload()
    return 'That move is no longer allowed, because the status changed first. The list shows the latest status.'
  }
  return NO_RESPONSE
}
