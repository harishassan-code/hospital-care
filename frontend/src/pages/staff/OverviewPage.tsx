import { AttentionList } from '../../features/overview/AttentionList'
import { DischargesToday } from '../../features/overview/DischargesToday'
import { OccupancyChart } from '../../features/overview/OccupancyChart'
import { RedCellChart } from '../../features/overview/RedCellChart'
import { StatusTiles } from '../../features/overview/StatusTiles'
import { canSee } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useScrollToHash } from '../../lib/useScrollToHash'
import { StaffDataState } from './StaffDataState'
import styles from './StaffPages.module.css'

export default function OverviewPage() {
  const { data, role } = useStaff()
  useScrollToHash(data !== null)
  if (!data) return <StaffDataState />

  return (
    <div className={styles.stack}>
      <StatusTiles data={data} />
      <div className={styles.split}>
        <AttentionList />
        <div className={styles.stack}>
          {canSee(role, 'beds') && <OccupancyChart data={data} />}
          {canSee(role, 'blood') && <RedCellChart data={data} />}
        </div>
      </div>
      {canSee(role, 'beds') && <DischargesToday data={data} />}
    </div>
  )
}
