import { useState } from 'react'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { MedicineTable } from '../../features/pharmacy/MedicineTable'
import { EXPIRING_WITHIN_DAYS, filterMedicines, type PharmacyFilter } from '../../features/pharmacy/pharmacy'
import pharmacyStyles from '../../features/pharmacy/Pharmacy.module.css'
import { useStaff } from '../../features/staff/staffContext'
import { StaffDataState } from './StaffDataState'
import styles from './StaffPages.module.css'

const FILTERS: { value: PharmacyFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'reorder', label: 'Needs reorder' },
  { value: 'expiring', label: `Expiring ≤ ${EXPIRING_WITHIN_DAYS} days` },
  { value: 'highAlert', label: 'High-alert' },
  { value: 'controlled', label: 'Controlled drugs' },
]

export default function PharmacyPage() {
  const { data, now } = useStaff()
  const [filter, setFilter] = useState<PharmacyFilter>('all')
  const [query, setQuery] = useState('')

  if (!data) return <StaffDataState />

  const sorted = [...data.medicines].sort((a, b) => a.name.localeCompare(b.name))
  const shown = filterMedicines(sorted, filter, query, now)
  const options = FILTERS.map((f) => ({ ...f, count: filterMedicines(sorted, f.value, '', now).length }))

  return (
    <div className={styles.stack}>
      <Panel title="Stock" aside={<span className={styles.note}>{shown.length} medicines</span>}>
        <div className={styles.toolbar}>
          <label className={pharmacyStyles.search}>
            Search medicines
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Name or category" />
          </label>
          <FilterBar label="Show" options={options} value={filter} onChange={setFilter} />
        </div>
        <MedicineTable medicines={shown} now={now} />
        <p className={styles.note}>
          High-alert medicines (ISMP list) carry a heightened risk of harm when used in error. CD = controlled drug:
          kept in the CD cabinet, every movement checked and signed by two people.
        </p>
      </Panel>
    </div>
  )
}
