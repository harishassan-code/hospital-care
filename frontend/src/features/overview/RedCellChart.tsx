import { BLOOD_GROUPS, MINIMUM_STOCK } from '../../api/blood'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { availableCounts, formatGroup, stockLevel } from '../blood/blood'
import type { StaffData } from '../staff/staffContext'
import styles from './Overview.module.css'

const LEVEL_LABEL = { low: 'Low', critical: 'Critical' } as const

/** Available red-cell units per group against each group's minimum (the tick). */
export function RedCellChart({ data }: { data: StaffData }) {
  const counts = availableCounts(data.units).redCells
  const scale = Math.max(...BLOOD_GROUPS.map((g) => Math.max(counts[g], MINIMUM_STOCK.redCells[g])))
  const pct = (n: number) => `${(n / scale) * 100}%`

  return (
    <Panel title="Red-cell stock by group" aside={<span className={styles.count}>Tick marks the minimum</span>}>
      <ul className={styles.bars} aria-label="Blood groups">
        {BLOOD_GROUPS.map((group) => {
          const count = counts[group]
          const minimum = MINIMUM_STOCK.redCells[group]
          const level = stockLevel(count, minimum)
          return (
            <li key={group} className={styles.barRow}>
              <span className={`${styles.barName} ${styles.group}`}>{formatGroup(group)}</span>
              <span className={styles.track} aria-hidden="true">
                <span className={styles.fill} style={{ width: pct(count) }} />
                <span className={styles.tick} style={{ left: pct(minimum) }} />
              </span>
              <span className={styles.barValue}>
                {count} <span className={styles.minimum}>/ min {minimum}</span>
                {level !== 'ok' && <StatusBadge tone={level === 'critical' ? 'critical' : 'warning'}>{LEVEL_LABEL[level]}</StatusBadge>}
              </span>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
