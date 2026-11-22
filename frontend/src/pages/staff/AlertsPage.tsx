import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { getNotifications, markAllRead, markRead, type AppNotification } from '../../api/notifications'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge, type Tone } from '../../components/ui/StatusBadge'
import formStyles from '../../features/blood/Blood.module.css'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

const TONE: Record<AppNotification['severity'], Tone> = { info: 'neutral', warning: 'warning', critical: 'critical' }

/** Every notification for me (story #53), newest first, with read state. */
export default function AlertsPage() {
  const load = useCallback(() => getNotifications(), [])
  const { result, setData } = useLoad(load)
  const [filter, setFilter] = useState<'all' | 'unread'>('all')

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />
  const items = result.data
  const shown = items.filter((n) => filter === 'all' || !n.read)
  const read = (id: number) => {
    void markRead(id).catch(() => undefined)
    setData((current) => current.map((n) => (n.id === id ? { ...n, read: true } : n)))
  }
  const readAll = async () => {
    await markAllRead().catch(() => undefined)
    setData((current) => current.map((n) => ({ ...n, read: true })))
  }

  return (
    <div className={pageStyles.stack}>
      <Panel title="Notifications">
        <div className={pageStyles.toolbar}>
          <FilterBar
            label="Show"
            options={[
              { value: 'all' as const, label: 'All', count: items.length },
              { value: 'unread' as const, label: 'Unread', count: items.filter((n) => !n.read).length },
            ]}
            value={filter}
            onChange={setFilter}
          />
          <button type="button" className={formStyles.more} onClick={readAll}>
            Mark all read
          </button>
        </div>
        {shown.length === 0 ? (
          <p>Nothing to show.</p>
        ) : (
          <ul aria-label="Notifications">
            {shown.map((n) => (
              <li key={n.id}>
                <StatusBadge tone={TONE[n.severity]}>{n.severity}</StatusBadge>{' '}
                {n.link ? (
                  <Link to={n.link} onClick={() => read(n.id)}>
                    {n.read ? n.title : <strong>{n.title}</strong>}
                  </Link>
                ) : (
                  n.title
                )}{' '}
                <small>
                  {n.body} · {new Date(n.createdAt).toLocaleString()}
                </small>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  )
}
