import { useState } from 'react'
import {
  AMBULANCE_STATUSES,
  AMBULANCE_TYPES,
  getAmbulances,
  type Ambulance,
  type AmbulanceStatus,
  type AmbulanceType,
} from '../../api/ambulances'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge, type Tone } from '../../components/ui/StatusBadge'
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
  inUse: 'neutral',
  maintenance: 'warning',
  outOfService: 'critical',
}

const statusLabel = (s: AmbulanceStatus) => AMBULANCE_STATUSES.find((x) => x.value === s)!.label
const typeLabel = (t: AmbulanceType) => AMBULANCE_TYPES.find((x) => x.value === t)!.label

/** Ambulance registry (story #50). */
export default function AmbulancesPage() {
  const { role } = useStaff()
  const { result, setData } = useLoad(getAmbulances)
  const [type, setType] = useState<TypeFilter>('all')
  const [status, setStatus] = useState<StatusFilter>('all')

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const items = result.data
  const editable = canEdit(role, 'ambulances')
  const shown = items.filter((e) => (type === 'all' || e.type === type) && (status === 'all' || e.status === status))
  const typeOptions = [{ value: 'all' as const, label: 'All' }, ...AMBULANCE_TYPES].map((o) => ({
    ...o,
    count: items.filter((e) => o.value === 'all' || e.type === o.value).length,
  }))
  const statusOptions = [{ value: 'all' as const, label: 'Any status' }, ...AMBULANCE_STATUSES].map((o) => ({
    ...o,
    count: items.filter((e) => (type === 'all' || e.type === type) && (o.value === 'all' || e.status === o.value)).length,
  }))
  const available = items.filter((e) => e.status === 'available').length

  return (
    <div className={pageStyles.stack}>
      {editable && <RegisterAmbulanceForm onRegistered={(item) => setData((current) => [...current, item])} />}
      <Panel title="Ambulances">
        <p>
          {available} of {items.length} available right now.
        </p>
        <FilterBar label="Show ambulance type" options={typeOptions} value={type} onChange={setType} />
        <FilterBar label="Show status" options={statusOptions} value={status} onChange={setStatus} />
        {items.length === 0 ? (
          <p>No ambulances registered yet.</p>
        ) : shown.length === 0 ? (
          <p>No ambulances match. Choose another type or status.</p>
        ) : (
          <table className={pageStyles.table}>
            <thead>
              <tr>
                <th scope="col">Call sign</th>
                <th scope="col">Type</th>
                <th scope="col">Base hospital</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((item) => (
                <tr key={item.id}>
                  <td>{item.identifier}</td>
                  <td>{typeLabel(item.type)}</td>
                  <td>{item.hospital}</td>
                  <td>
                    <StatusBadge tone={TONE[item.status]}>{statusLabel(item.status)}</StatusBadge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  )
}