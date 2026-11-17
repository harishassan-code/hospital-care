import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { getFeed, SEVERITIES, type FeedEntry, type FeedType } from '../../api/emergencies'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { CaseStatusLabel } from '../../features/emergencies/CaseStatusLabel'
import { describeNeed, SEVERITY_TONE } from '../../features/emergencies/emergencies'
import styles from '../../features/emergencies/Emergencies.module.css'
import { useStaff } from '../../features/staff/staffContext'
import { formatAgo } from '../../lib/time'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

const TYPES: readonly { id: FeedType; label: string }[] = [
  { id: 'blood', label: 'Blood' },
  { id: 'bed', label: 'Beds' },
]

/**
 * Active emergency requests from every hospital, most urgent first (story #36). A request at the user's own hospital
 * links to its case; another hospital's has no link, because the server would answer 404 for it.
 */
export default function EmergencyFeedPage() {
  const [type, setType] = useState<FeedType>('blood')
  return (
    <div className={pageStyles.stack}>
      <Link to="/staff/emergencies" className={styles.back}>
        ← All emergency cases
      </Link>
      <Panel title="Network requests">
        <p>Active requests from every hospital, most urgent first. Your own hospital’s requests link to their case.</p>
        <fieldset className={styles.toggle}>
          <legend>Show</legend>
          {TYPES.map((t) => (
            <label key={t.id}>
              <input type="radio" name="feed-type" value={t.id} checked={type === t.id} onChange={() => setType(t.id)} />
              {t.label}
            </label>
          ))}
        </fieldset>
        {/* Keyed by type: each toggle loads that type again, from the top. */}
        <FeedList key={type} type={type} />
      </Panel>
    </div>
  )
}

function FeedList({ type }: { type: FeedType }) {
  const { user, now } = useStaff()
  const load = useCallback(() => getFeed(type), [type])
  const { result } = useLoad(load)

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  if (result.data.length === 0) {
    return <p>{type === 'blood' ? 'No blood requests in the network right now.' : 'No bed requests in the network right now.'}</p>
  }

  return (
    <ol className={styles.feed} aria-label={type === 'blood' ? 'Blood requests' : 'Bed requests'}>
      {result.data.map((entry) => (
        <FeedItem key={entry.reference} entry={entry} now={now} own={entry.hospital !== null && entry.hospital.id === user.hospital?.id} />
      ))}
    </ol>
  )
}

function FeedItem({ entry, now, own }: { entry: FeedEntry; now: Date; own: boolean }) {
  const severity = SEVERITIES.find((s) => s.id === entry.severity)?.label
  return (
    <li className={styles.entry} data-severity={entry.severity}>
      <div className={styles.entryHead}>
        <strong>{entry.hospital?.name ?? 'No hospital'}</strong>
        {own ? (
          <Link to={`/staff/emergencies/${encodeURIComponent(entry.reference)}`} className={styles.reference}>
            {entry.reference}
          </Link>
        ) : (
          <span className={styles.reference}>{entry.reference}</span>
        )}
      </div>
      <div className={styles.entryMeta}>
        <StatusBadge tone={SEVERITY_TONE[entry.severity]}>{severity}</StatusBadge>
        <CaseStatusLabel status={entry.status} />
        <time dateTime={entry.createdAt}>{formatAgo(entry.createdAt, now)}</time>
      </div>
      <p className={styles.needsLine}>
        {entry.needs.map((need) => `${describeNeed(need)}${need.fulfilled ? ` (${need.fulfilled} filled)` : ''}`).join(', ')}
      </p>
    </li>
  )
}
