import { CompatibilityFinder } from '../../features/blood/CompatibilityFinder'
import { StockGrid } from '../../features/blood/StockGrid'
import { StorageGuide } from '../../features/blood/StorageGuide'
import { UnitTable } from '../../features/blood/UnitTable'
import { useStaff } from '../../features/staff/staffContext'
import { StaffDataState } from './StaffDataState'
import styles from './StaffPages.module.css'

export default function BloodPage() {
  const { data, now } = useStaff()
  if (!data) return <StaffDataState />

  return (
    <div className={styles.stack}>
      <StockGrid units={data.units} />
      <div className={styles.split}>
        <CompatibilityFinder units={data.units} />
        <StorageGuide />
      </div>
      <UnitTable units={data.units} now={now} />
    </div>
  )
}
