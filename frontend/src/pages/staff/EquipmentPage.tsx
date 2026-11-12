import { useState } from 'react'
import { EQUIPMENT_STATUSES, EQUIPMENT_TYPES, getEquipment, type Equipment, type EquipmentStatus, type EquipmentType } from '../../api/equipment'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge, type Tone } from '../../components/ui/StatusBadge'
import { RegisterEquipmentForm } from '../../features/equipment/RegisterEquipmentForm'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

type TypeFilter = 'all' | EquipmentType
type StatusFilter = 'all' | EquipmentStatus

const TONE: Record<EquipmentStatus, Tone> = { available: 'ok', inUse: 'neutral', maintenance: 'warning', outOfService: 'critical' }
const statusLabel = (s: EquipmentStatus) => EQUIPMENT_STATUSES.find((x) => x.value === s)!.label
const typeLabel = (t: EquipmentType) => EQUIPMENT_TYPES.find((x) => x.value === t)!.label.replace(/s$/, '')

/** Equipment registry (story #26): critical equipment with type, asset tag, location and status. */
export default function EquipmentPage() {
  const { role } = useStaff()
  const { result, setData } = useLoad(getEquipment)
  const [type, setType] = useState<TypeFilter>('all')
  const [status, setStatus] = useState<StatusFilter>('all')

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const items = result.data
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

  return (
    <div className={pageStyles.stack}>
      {canEdit(role, 'equipment') && (
        <RegisterEquipmentForm onRegistered={(item) => setData((current) => [...current, item])} />
      )}
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
