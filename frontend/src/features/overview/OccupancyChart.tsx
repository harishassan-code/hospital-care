import type { BedStatus } from '../../api/beds'
import { Panel } from '../../components/ui/Panel'
import { STATUS_LABEL, summarize } from '../beds/beds'
import type { StaffData } from '../staff/staffContext'
import styles from './Overview.module.css'

/** Stack order and colour per bed status (palette validated with the dataviz checker). */
const SEGMENTS: readonly { status: BedStatus; color: string }[] = [
  { status: 'occupied', color: 'var(--bed-occupied)' },
  { status: 'reserved', color: 'var(--bed-reserved)' },
  { status: 'cleaning', color: 'var(--bed-cleaning)' },
  { status: 'free', color: 'var(--bed-free)' },
  { status: 'outOfService', color: 'var(--bed-out)' },
]

function Legend() {
  return (
    <ul className={styles.legend} aria-label="Legend">
      {SEGMENTS.map((s) => (
        <li key={s.status}>
          <span className={styles.swatch} style={{ background: s.color }} aria-hidden="true" />
          {STATUS_LABEL[s.status]}
        </li>
      ))}
    </ul>
  )
}

export function OccupancyChart({ data }: { data: StaffData }) {
  return (
    <Panel title="Bed occupancy by ward" aside={<Legend />}>
      <ul className={styles.bars} aria-label="Wards">
        {data.wards.map((ward) => {
          const counts = summarize(data.beds.filter((b) => b.ward === ward.id))
          const inService = counts.total - counts.outOfService
          const occupancy = inService ? Math.round((counts.occupied / inService) * 100) : 0
          const breakdown = SEGMENTS.map((s) => `${STATUS_LABEL[s.status]} ${counts[s.status]}`).join(', ')
          return (
            <li key={ward.id} className={styles.barRow}>
              <span className={styles.barName}>{ward.name}</span>
              <span className={styles.stack} aria-hidden="true">
                {SEGMENTS.filter((s) => counts[s.status] > 0).map((s) => (
                  <span
                    key={s.status}
                    className={styles.segment}
                    style={{ flexGrow: counts[s.status], background: s.color }}
                    title={`${STATUS_LABEL[s.status]}: ${counts[s.status]}`}
                  />
                ))}
              </span>
              <span className={styles.barValue}>
                {occupancy}% · {counts.free} free
              </span>
              <span className="visually-hidden">{breakdown}</span>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
