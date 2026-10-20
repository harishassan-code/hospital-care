import { CompatibilityFinder } from '../../features/blood/CompatibilityFinder'
import { RegisterUnitForm } from '../../features/blood/RegisterUnitForm'
import { ScreeningPanel } from '../../features/blood/ScreeningPanel'
import { StockGrid } from '../../features/blood/StockGrid'
import { StorageGuide } from '../../features/blood/StorageGuide'
import { UnitTable } from '../../features/blood/UnitTable'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { StaffDataState } from './StaffDataState'
import styles from './StaffPages.module.css'

export default function BloodPage() {
  const { data, now, role, upsertUnit } = useStaff()
  if (!data) return <StaffDataState />

  return (
    <div className={styles.stack}>
      <StockGrid units={data.units} />
      <div className={styles.split}>
        <CompatibilityFinder units={data.units} />
        <StorageGuide />
      </div>
      <UnitTable units={data.units} now={now} />
      {canEdit(role, 'blood') && (
        <>
          <ScreeningPanel units={data.units} onUpdated={upsertUnit} />
          <RegisterUnitForm now={now} onRegistered={upsertUnit} />
        </>
      )}
    </div>
  )
}
