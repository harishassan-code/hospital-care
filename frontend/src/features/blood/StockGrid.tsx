import { BLOOD_GROUPS, COMPONENTS, MINIMUM_STOCK, type BloodUnit } from '../../api/blood'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { availableCounts, formatGroup, stockLevel } from './blood'
import styles from './Blood.module.css'

/** Available units per component and group against each minimum. */
export function StockGrid({ units }: { units: BloodUnit[] }) {
  const counts = availableCounts(units)

  return (
    <Panel title="Stock">
      <div className="table-scroll">
        <table className={styles.grid}>
          <caption className="visually-hidden">Available units by component and group, with each minimum</caption>
          <thead>
            <tr>
              <th scope="col">Component</th>
              {BLOOD_GROUPS.map((g) => (
                <th key={g} scope="col" className={styles.groupHead}>
                  {formatGroup(g)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COMPONENTS.map((c) => (
              <tr key={c.id}>
                <th scope="row">{c.label}</th>
                {BLOOD_GROUPS.map((g) => {
                  const count = counts[c.id][g]
                  const minimum = MINIMUM_STOCK[c.id][g]
                  const level = stockLevel(count, minimum)
                  return (
                    <td key={g} className={styles.cell} data-level={level}>
                      <span className={styles.count}>{count}</span>
                      <span className={styles.minimum}>min {minimum}</span>
                      {level !== 'ok' && (
                        <StatusBadge tone={level === 'critical' ? 'critical' : 'warning'}>
                          {level === 'critical' ? 'Critical' : 'Low'}
                        </StatusBadge>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}
