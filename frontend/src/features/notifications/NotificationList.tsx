import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Notification } from '../../api/notifications'
import { hospital } from '../../config/hospital'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatAgo, formatClock } from '../../lib/time'
import { useStaff } from '../staff/staffContext'
import type { NotificationFeed } from './useNotificationFeed'
import styles from './Notifications.module.css'

/** Shown while the first answer is on its way, or when it never came (the same words as the staff pages). */
export function FeedLoading({ feed }: { feed: NotificationFeed }) {
  return (
    <p role="status">
      {feed.failed
        ? `The hospital’s system didn’t respond. Reload the page, or call ${hospital.mainPhone} if it keeps happening.`
        : 'Loading…'}
    </p>
  )
}

/** Says a refresh failed and which time the list is from. Nothing is shown while the list is current. */
export function FeedNotice({ feed }: { feed: NotificationFeed }) {
  if (!feed.refreshFailed || !feed.updatedAt) return null
  return <p className={styles.notice}>{`Couldn’t update alerts. Showing alerts from ${formatClock(feed.updatedAt)}.`}</p>
}

/** Marks one alert read. A failure is said beside the button, and the alert stays unread. */
export function MarkReadButton({ notification, label = 'Mark read' }: { notification: Notification; label?: string }) {
  const { notifications } = useStaff()
  const [pending, setPending] = useState(false)
  const [failed, setFailed] = useState(false)

  async function markRead() {
    setPending(true)
    setFailed(false)
    try {
      await notifications.markRead(notification.id)
    } catch {
      setFailed(true)
    } finally {
      setPending(false)
    }
  }

  return (
    <>
      <button
        type="button"
        className={styles.action}
        aria-label={`${label}: ${notification.message}`}
        disabled={pending}
        onClick={markRead}
      >
        {label}
      </button>
      {failed && (
        <span role="alert" className={styles.error}>
          This alert couldn’t be marked as read. Try again.
        </span>
      )}
    </>
  )
}

/** One notification: its severity, read state, time, message, and the page it links to. */
export function NotificationRow({ notification }: { notification: Notification }) {
  const { now } = useStaff()
  const unread = notification.readAt === null
  return (
    <div className={styles.row}>
      <div className={styles.meta}>
        {notification.severity === 'critical' && <StatusBadge tone="critical">Critical</StatusBadge>}
        {unread && <span className={styles.unread}>Unread</span>}
        <time dateTime={notification.createdAt}>{formatAgo(notification.createdAt, now)}</time>
      </div>
      <p className={styles.message}>{notification.message}</p>
      {(notification.link || unread) && (
        <div className={styles.actions}>
          {notification.link && (
            <Link to={notification.link} className={styles.action} aria-label={`Open: ${notification.message}`}>
              Open
            </Link>
          )}
          {unread && <MarkReadButton notification={notification} />}
        </div>
      )}
    </div>
  )
}
