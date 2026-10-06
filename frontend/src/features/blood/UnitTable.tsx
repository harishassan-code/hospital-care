import { useState } from 'react'
import { COMPONENTS, type BloodUnit, type Component, type UnitStatus } from '../../api/blood'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatDuration, formatShortDate, hoursUntil } from '../../lib/time'
import { COMPONENT_LABEL, formatGroup, sortFefo, UNIT_STATUS_LABEL } from './blood'
import styles from './Blood.module.css'

const PAGE = 25
const STATUSES: UnitStatus[] = ['available', 'quarantined', 'reserved', 'issued', 'expired']

function Expiry({ iso, now }: { iso: string; now: Date }) {
  const hours = hoursUntil(iso, now)
  if (hours <= 0) return <StatusBadge tone="critical">{`Expired ${formatDuration(-hours * 60)} ago`}</StatusBadge>
  const text = `in ${formatDuration(hours * 60)}`
  return hours <= 24 ? <StatusBadge tone="warning">{text}</StatusBadge> : <>{text}</>
}

/** Every unit, first-expiry-first-out, so the next unit to use is always at the top. */
export function UnitTable({ units, now }: { units: BloodUnit[]; now: Date }) {
  const [component, setComponent] = useState<'all' | Component>('all')
  const [status, setStatus] = useState<'all' | UnitStatus>('available')
  const [limit, setLimit] = useState(PAGE)

  const byStatus = units.filter((u) => status === 'all' || u.status === status)
  const shown = sortFefo(byStatus.filter((u) => component === 'all' || u.component === component))
  const countFor = (c: Component) => byStatus.filter((u) => u.component === c).length

  return (
    <Panel title="Units" aside={<span className={styles.note}>{shown.length} units · soonest expiry first</span>}>
      <div className={styles.filters}>
        <FilterBar
          label="Status"
          options={[{ value: 'all', label: 'All' }, ...STATUSES.map((s) => ({ value: s, label: UNIT_STATUS_LABEL[s] }))]}
          value={status}
          onChange={(s) => {
            setStatus(s)
            setLimit(PAGE)
          }}
        />
        <FilterBar
          label="Component"
          options={[
            { value: 'all', label: 'All', count: byStatus.length },
            ...COMPONENTS.map((c) => ({ value: c.id, label: c.label, count: countFor(c.id) })),
          ]}
          value={component}
          onChange={(c) => {
            setComponent(c)
            setLimit(PAGE)
          }}
        />
      </div>

      <div className="table-scroll">
        <table className={styles.units}>
          <caption className="visually-hidden">Blood units, soonest expiry first</caption>
          <thead>
            <tr>
              <th scope="col">Unit number</th>
              <th scope="col">Group</th>
              <th scope="col">Component</th>
              <th scope="col">Collected</th>
              <th scope="col">Expires</th>
              <th scope="col">Status</th>
              <th scope="col">Storage</th>
            </tr>
          </thead>
          <tbody>
            {shown.slice(0, limit).map((u) => (
              <tr key={u.id} data-expires={new Date(u.expiresAt).getTime()}>
                <td className={styles.mono}>{u.id}</td>
                <td className={styles.mono}>{formatGroup(u.group)}</td>
                <td>{COMPONENT_LABEL[u.component]}</td>
                <td>{formatShortDate(new Date(u.collectedAt))}</td>
                <td>
                  <Expiry iso={u.expiresAt} now={now} />
                </td>
                <td>{UNIT_STATUS_LABEL[u.status]}</td>
                <td>{u.location}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {shown.length > limit && (
        <button type="button" className={styles.more} onClick={() => setLimit((l) => l + PAGE)}>
          Show {Math.min(PAGE, shown.length - limit)} more
        </button>
      )}
    </Panel>
  )
}
