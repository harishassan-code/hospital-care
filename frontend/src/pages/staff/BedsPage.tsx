import { useState } from 'react'
import type { BedStatus, WardId } from '../../api/beds'
import { FormAlert } from '../../components/form/FormAlert'
import { FilterBar } from '../../components/ui/FilterBar'
import { actionsFor, dischargesToday, STATUS_LABEL, summarize, type BedAction } from '../../features/beds/beds'
import { BedTile } from '../../features/beds/BedTile'
import styles from '../../features/beds/Beds.module.css'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

type StatusFilter = 'all' | BedStatus | 'dischargeToday'

const STATUS_ORDER: BedStatus[] = ['free', 'cleaning', 'reserved', 'occupied', 'outOfService']

export default function BedsPage() {
  const { data, role, now, updateBed } = useStaff()
  const [ward, setWard] = useState<'all' | WardId>('all')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [announcement, setAnnouncement] = useState('')
  const [error, setError] = useState<string>()

  if (!data) return <StaffDataState />

  const editable = canEdit(role, 'beds')
  const leavingToday = new Set(dischargesToday(data.beds, now).map((b) => b.id))
  const counts = summarize(data.beds)
  const matches = (bedId: string, bedStatus: BedStatus) =>
    status === 'all' || (status === 'dischargeToday' ? leavingToday.has(bedId) : bedStatus === status)

  /** Save the change, then announce it only if the server accepted it. */
  const act = async (bedId: string, label: string, from: BedStatus, action: BedAction) => {
    setError(undefined)
    const next = actionsFor(from).find((t) => t.action === action)?.next
    const result = await updateBed(bedId, action)
    if (!result.ok) setError(`${label}: ${result.message}`)
    else if (next) setAnnouncement(`${label} is now ${STATUS_LABEL[next].toLowerCase()}`)
  }

  const wards = ward === 'all' ? data.wards : data.wards.filter((w) => w.id === ward)

  return (
    <div className={pageStyles.stack}>
      <div className={styles.filters}>
        <FilterBar
          label="Ward"
          options={[{ value: 'all', label: 'All wards' }, ...data.wards.map((w) => ({ value: w.id, label: w.name }))]}
          value={ward}
          onChange={setWard}
        />
        <FilterBar<StatusFilter>
          label="Status"
          options={[
            { value: 'all', label: 'All', count: counts.total },
            ...STATUS_ORDER.map((s) => ({ value: s, label: STATUS_LABEL[s], count: counts[s] })),
            { value: 'dischargeToday', label: 'Discharging today', count: leavingToday.size },
          ]}
          value={status}
          onChange={setStatus}
        />
        {!editable && <p className={pageStyles.note}>View only: your role can’t change bed status.</p>}
      </div>

      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {announcement}
      </p>

      {wards.map((w) => {
        const wardBeds = data.beds.filter((b) => b.ward === w.id)
        const shown = wardBeds.filter((b) => matches(b.id, b.status))
        if (status !== 'all' && shown.length === 0) return null
        const c = summarize(wardBeds)
        const inService = c.total - c.outOfService
        const occupancy = inService ? Math.round((c.occupied / inService) * 100) : 0
        return (
          <section key={w.id} className={styles.ward} aria-labelledby={`ward-${w.id}`}>
            <header className={styles.wardHead}>
              <h2 id={`ward-${w.id}`} className={styles.wardName}>
                {w.name} <span className={styles.wardKind}>{w.kind}</span>
              </h2>
              <p className={styles.wardStats}>
                {occupancy}% occupied · {c.free} free · {c.total} beds
              </p>
            </header>
            <ul className={styles.grid}>
              {shown.map((bed) => (
                <BedTile
                  key={bed.id}
                  bed={bed}
                  now={now}
                  editable={editable}
                  onAction={(action) => act(bed.id, bed.label, bed.status, action)}
                />
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}
