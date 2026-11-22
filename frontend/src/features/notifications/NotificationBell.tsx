import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useStaff } from '../staff/staffContext'
import { FeedLoading, FeedNotice, NotificationRow } from './NotificationList'
import styles from './Notifications.module.css'

/** How many unread notifications the bell panel lists. The alerts page has them all. */
const PANEL_LIMIT = 10

/**
 * The bell in the top bar (B07, #53). Its badge counts unread notifications plus the attention items the browser works
 * out. Its name says both counts in words. The button opens a panel of unread notifications; Escape or a second press
 * closes it, and so does moving to another page.
 */
export function NotificationBell() {
  const { attention, notifications: feed } = useStaff()
  const [open, setOpen] = useState(false)
  const bell = useRef<HTMLButtonElement>(null)
  const { pathname } = useLocation()
  // Moving to another page closes the panel. Adjusting state while rendering avoids an effect that sets state.
  const [shownPath, setShownPath] = useState(pathname)
  if (shownPath !== pathname) {
    setShownPath(pathname)
    setOpen(false)
  }

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setOpen(false)
      bell.current?.focus()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open])

  const unread = feed.unreadCount
  const items = attention.length
  const badge = unread + items
  const name = `${unread} unread ${unread === 1 ? 'notification' : 'notifications'} and ${items} ${items === 1 ? 'item needs' : 'items need'} attention`

  return (
    <div className={styles.bellWrap}>
      <button
        ref={bell}
        type="button"
        className={styles.bell}
        aria-label={name}
        aria-expanded={open}
        aria-controls="alerts-panel"
        onClick={() => setOpen((current) => !current)}
      >
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <path d="M12 3a6 6 0 0 0-6 6v4l-2 3h16l-2-3V9a6 6 0 0 0-6-6Zm-2.5 15a2.5 2.5 0 0 0 5 0" fill="none" stroke="currentColor" strokeWidth="2" />
        </svg>
        {badge > 0 && <span className={styles.bellCount}>{badge > 99 ? '99+' : badge}</span>}
      </button>

      <section id="alerts-panel" aria-labelledby="alerts-panel-title" hidden={!open} className={styles.panel}>
        <h2 id="alerts-panel-title" className={styles.heading}>
          Unread alerts
        </h2>
        <FeedNotice feed={feed} />
        {feed.unread === null ? (
          <FeedLoading feed={feed} />
        ) : feed.unread.length === 0 ? (
          <p>No unread notifications.</p>
        ) : (
          <ul className={styles.list}>
            {feed.unread.slice(0, PANEL_LIMIT).map((n) => (
              <li key={n.id}>
                <NotificationRow notification={n} />
              </li>
            ))}
          </ul>
        )}
        <p className={styles.footer}>
          <Link to="/staff/alerts">All alerts</Link>
          {items > 0 && (
            <>
              {' · '}
              <Link to="/staff#attention">Needs attention</Link>
            </>
          )}
        </p>
      </section>
    </div>
  )
}
