import { useState } from 'react'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { FeedLoading, FeedNotice, NotificationRow } from '../../features/notifications/NotificationList'
import styles from '../../features/notifications/Notifications.module.css'
import { useStaff } from '../../features/staff/staffContext'
import pageStyles from './StaffPages.module.css'

type Filter = 'all' | 'unread'

const FILTERS: readonly { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'unread', label: 'Unread' },
]

/**
 * Every notification for the signed-in user, newest first, read and unread (B07, #53). Marking one read here updates the
 * bell and the banners at once, because they share one feed.
 */
export default function AlertsPage() {
  const { notifications: feed } = useStaff()
  const [filter, setFilter] = useState<Filter>('all')

  if (feed.all === null || feed.unread === null) {
    return (
      <div className={pageStyles.stack}>
        <Panel title="Your alerts" id="alerts">
          <FeedLoading feed={feed} />
        </Panel>
      </div>
    )
  }

  const rows = filter === 'all' ? feed.all : feed.unread
  return (
    <div className={pageStyles.stack}>
      <Panel title="Your alerts" id="alerts">
        <FeedNotice feed={feed} />
        <FilterBar label="Show alerts" options={FILTERS} value={filter} onChange={setFilter} />
        {rows.length === 0 ? (
          <p>{filter === 'all' ? 'No notifications yet.' : 'No unread notifications.'}</p>
        ) : (
          <ul className={styles.list}>
            {rows.map((n) => (
              <li key={n.id}>
                <NotificationRow notification={n} />
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  )
}
