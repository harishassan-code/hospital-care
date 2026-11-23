import { ER_STATUS_LABEL, type EmergencyNow } from '../../api/public'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { ER_TONE } from './network'
import styles from './Network.module.css'

/** A hospital's emergency department in one line: status, wait and people waiting, or that it hasn't reported. */
export function ErStatusLine({ emergency }: { emergency: EmergencyNow | null }) {
  if (!emergency) return <StatusBadge tone="neutral">Emergency status not reported</StatusBadge>
  return (
    <span className={styles.erLine}>
      <StatusBadge tone={ER_TONE[emergency.status]}>{ER_STATUS_LABEL[emergency.status]}</StatusBadge>
      {emergency.status !== 'diverting' && (
        <span className={styles.wait}>
          <strong>{emergency.waitMinutes} min</strong> wait
        </span>
      )}
    </span>
  )
}
