import { formatClock } from '../../lib/time'
import { useStaff } from '../staff/staffContext'
import styles from './Overview.module.css'

/** When the figures were last loaded. Words say when a reload failed, so the state doesn't depend on colour. */
export function LastUpdated() {
  const { updatedAt, refreshFailed } = useStaff()
  const text = !updatedAt
    ? ''
    : refreshFailed
      ? `Couldn’t update. Showing data from ${formatClock(updatedAt)}.`
      : `Updated ${formatClock(updatedAt)}`
  return (
    <p role="status" className={styles.updated}>
      {text}
    </p>
  )
}
