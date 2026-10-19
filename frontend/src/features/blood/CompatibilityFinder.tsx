import { useState } from 'react'
import { BLOOD_GROUPS, type BloodGroup, type BloodUnit } from '../../api/blood'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { availableCounts, compatibleDonors, formatGroup } from './blood'
import styles from './Blood.module.css'

type FinderComponent = 'redCells' | 'plasma'

const OPTIONS = [
  { value: 'redCells', label: 'Red cells' },
  { value: 'plasma', label: 'Plasma' },
] as const

/** Which donor groups a patient can receive, and how many of each are on the shelf now. */
export function CompatibilityFinder({ units }: { units: BloodUnit[] }) {
  const [recipient, setRecipient] = useState<BloodGroup>('O+')
  const [component, setComponent] = useState<FinderComponent>('redCells')
  const counts = availableCounts(units)[component]
  const donors = compatibleDonors(recipient, component)
  const total = donors.reduce((sum, g) => sum + counts[g], 0)
  const noun = component === 'redCells' ? 'red-cell' : 'plasma'

  return (
    <Panel title="Compatibility finder">
      <div className={styles.finderControls}>
        <label className={styles.selectField}>
          Patient’s blood group
          <select value={recipient} onChange={(e) => setRecipient(e.target.value as BloodGroup)}>
            {BLOOD_GROUPS.map((g) => (
              <option key={g} value={g}>
                {formatGroup(g)}
              </option>
            ))}
          </select>
        </label>
        <FilterBar label="Component" options={OPTIONS} value={component} onChange={setComponent} />
      </div>

      <p className={styles.finderTotal} aria-live="polite">
        <strong>{total}</strong> compatible {noun} units available for a {formatGroup(recipient)} patient
      </p>
      <ul className={styles.donors} aria-label="Compatible donor groups">
        {donors.map((g) => (
          <li key={g} className={styles.donor} data-same={g === recipient}>
            <strong>{formatGroup(g)}</strong>
            <span>{counts[g]} units</span>
            {g === recipient && <span className={styles.preferred}>Same group: use first</span>}
          </li>
        ))}
      </ul>
      <p className={styles.disclaimer}>
        Coordination aid only: the lab confirms compatibility with a crossmatch before any transfusion.
      </p>
    </Panel>
  )
}
