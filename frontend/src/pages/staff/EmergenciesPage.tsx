import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCases, SEVERITIES, type EmergencyCase } from '../../api/emergencies'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { BloodRequestForm } from '../../features/emergencies/BloodRequestForm'
import { CaseStatusLabel } from '../../features/emergencies/CaseStatusLabel'
import { describeNeed, SEVERITY_TONE } from '../../features/emergencies/emergencies'
import styles from '../../features/emergencies/Emergencies.module.css'
import { NewCaseForm } from '../../features/emergencies/NewCaseForm'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { formatClock, formatShortDate } from '../../lib/time'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

/**
 * Emergency cases at the user's hospital, opening a new one (stories #30, #32), a quick blood request (#36), and
 * the network feed. The server orders the list (#31).
 */
export default function EmergenciesPage() {
  const { role } = useStaff()
  const { result, setData } = useLoad(getCases)
  const [creating, setCreating] = useState(false)
  const [requesting, setRequesting] = useState(false)
  const [opened, setOpened] = useState<string>()
  const newCase = useRef<HTMLButtonElement>(null)
  const wasCreating = useRef(false)
  const requestBlood = useRef<HTMLButtonElement>(null)
  const wasRequesting = useRef(false)

  // When a form closes (opened or cancelled), put focus back on the button that opened it.
  useEffect(() => {
    if (wasCreating.current && !creating) newCase.current?.focus()
    wasCreating.current = creating
  }, [creating])
  useEffect(() => {
    if (wasRequesting.current && !requesting) requestBlood.current?.focus()
    wasRequesting.current = requesting
  }, [requesting])

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const editable = canEdit(role, 'emergencies')

  async function handleCreated(created: EmergencyCase) {
    setCreating(false)
    setOpened(created.id)
    // Take the server's order (severity, then age) rather than placing the new case here.
    try {
      const cases = await getCases()
      setData(() => cases)
    } catch {
      // The case is open either way; the list catches up on the next visit.
    }
  }

  return (
    <div className={pageStyles.stack}>
      {creating && <NewCaseForm onCreated={handleCreated} onClose={() => setCreating(false)} />}
      {requesting && <BloodRequestForm onClose={() => setRequesting(false)} />}
      <Panel
        title="Emergency cases"
        aside={
          <div className={styles.asides}>
            <Link to="/staff/emergencies/feed" className={styles.navLink}>
              Network requests
            </Link>
            {editable && !creating && !requesting && (
              <>
                <button
                  ref={newCase}
                  type="button"
                  className={styles.secondaryAction}
                  onClick={() => {
                    setOpened(undefined)
                    setCreating(true)
                  }}
                >
                  New case
                </button>
                <button ref={requestBlood} type="button" className={styles.secondaryAction} onClick={() => setRequesting(true)}>
                  Request blood
                </button>
              </>
            )}
          </div>
        }
      >
        <p role="status">{opened && `Case ${opened} is open.`}</p>
        {result.data.length === 0 ? (
          <p>No emergency cases yet.{editable && ' Open one with “New case”.'}</p>
        ) : (
          <div className="table-scroll">
            <table className={styles.table}>
              <caption className="visually-hidden">Emergency cases, most severe first, then oldest first</caption>
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Severity</th>
                  <th scope="col">Needs</th>
                  <th scope="col">Status</th>
                  <th scope="col">Opened</th>
                </tr>
              </thead>
              <tbody>
                {result.data.map((c) => (
                  <CaseRow key={c.id} item={c} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}

function CaseRow({ item }: { item: EmergencyCase }) {
  const opened = new Date(item.createdAt)
  return (
    <tr className={item.severity === 'critical' ? styles.critical : undefined}>
      <td>
        <Link to={`/staff/emergencies/${encodeURIComponent(item.id)}`} className={styles.reference}>
          {item.id}
        </Link>
        {item.patientRef && <div className={styles.hint}>{item.patientRef}</div>}
      </td>
      <td>
        <StatusBadge tone={SEVERITY_TONE[item.severity]}>{SEVERITIES.find((s) => s.id === item.severity)?.label}</StatusBadge>
      </td>
      <td>{item.items.map(describeNeed).join(', ')}</td>
      <td>
        <CaseStatusLabel status={item.status} />
      </td>
      <td>
        <time dateTime={item.createdAt}>
          {formatShortDate(opened)}, {formatClock(opened)}
        </time>
        <div className={styles.hint}>{item.createdBy}</div>
      </td>
    </tr>
  )
}
