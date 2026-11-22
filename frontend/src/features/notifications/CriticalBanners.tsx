import { Link } from 'react-router-dom'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { useStaff } from '../staff/staffContext'
import { MarkReadButton } from './NotificationList'
import styles from './Notifications.module.css'

/** Most critical banners on screen at once; the rest are a line with a link to the alerts page. */
const SHOWN = 3

/**
 * Unread critical alerts, shown on every staff page until someone acknowledges each one (B07, #53). Acknowledging is the
 * same call as Mark read. Nothing is drawn when no critical alert is unread.
 */
export function CriticalBanners() {
  const { notifications: feed } = useStaff()
  const critical = (feed.unread ?? []).filter((n) => n.severity === 'critical')
  if (critical.length === 0) return null
  const shown = critical.slice(0, SHOWN)
  const more = critical.length - shown.length

  return (
    <section aria-label="Critical alerts" className={styles.banners}>
      {shown.map((n) => (
        <div key={n.id} role="alert" className={styles.banner}>
          <StatusBadge tone="critical">Critical</StatusBadge>
          <p className={styles.message}>{n.message}</p>
          <div className={styles.actions}>
            {n.link && (
              <Link to={n.link} className={styles.action} aria-label={`Open: ${n.message}`}>
                Open
              </Link>
            )}
            <MarkReadButton notification={n} label="Acknowledge" />
          </div>
        </div>
      ))}
      {more > 0 && (
        <p className={styles.overflow}>
          {more} more critical {more === 1 ? 'alert' : 'alerts'}. <Link to="/staff/alerts">See all alerts</Link>
        </p>
      )}
    </section>
  )
}
