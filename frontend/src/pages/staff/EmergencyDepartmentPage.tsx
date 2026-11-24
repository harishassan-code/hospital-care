import { useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { getQueue, postVisitAction, type ErQueue, type ErVisit, type VisitAction } from '../../api/emergencies'
import { BarChart, ChartFrame, ChartGrid, SERIES, TimeSeriesChart } from '../../components/charts'
import { FormAlert } from '../../components/form/FormAlert'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge, type Tone } from '../../components/ui/StatusBadge'
import { frameState, points, tableRows, typicalFor, useMetrics } from '../../features/charts/useMetrics'
import { DepartmentStatusPanel } from '../../features/emergencies/DepartmentStatusPanel'
import bedStyles from '../../features/beds/Beds.module.css'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { StaffDataState } from './StaffDataState'
import styles from './EmergencyDepartmentPage.module.css'
import pageStyles from './StaffPages.module.css'

const REFRESH_MS = 30_000
const TRIAGE_LABEL = { 1: '1 · Resuscitation', 2: '2 · Emergent', 3: '3 · Urgent', 4: '4 · Less urgent', 5: '5 · Non-urgent' } as const
const TRIAGE_TONE: Record<number, Tone> = { 1: 'critical', 2: 'critical', 3: 'warning', 4: 'neutral', 5: 'neutral' }
const ACTION_LABEL: Record<VisitAction, string> = {
  startTreatment: 'Start treatment',
  discharge: 'Discharge',
  admit: 'Admit',
  transfer: 'Transfer',
  leaveUnseen: 'Left unseen',
}
const time = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' })

function minutes(n: number): string {
  return n < 60 ? `${n} min` : `${Math.floor(n / 60)} h ${n % 60} min`
}

/**
 * The emergency department (B22): who is waiting and who is next, in triage order; who is being treated and who
 * waits for a ward bed; and why the wait is what it is. Patients are tags and categories, never names.
 */
export default function EmergencyDepartmentPage() {
  const { role } = useStaff()
  const [queue, setQueue] = useState<ErQueue | null>(null)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState<number>()
  const [error, setError] = useState<string>()
  const [announcement, setAnnouncement] = useState('')
  const [reloadAt, setReloadAt] = useState(0)
  const editable = canEdit(role, 'emergencyDepartment')
  const arrivals = useMetrics({ metrics: ['er.arrivals', 'er.wait_minutes'], days: 1, typical: true })

  useEffect(() => {
    let active = true
    const load = () =>
      getQueue()
        .then((next) => {
          if (!active) return
          setQueue(next)
          setFailed(false)
        })
        .catch(() => active && setFailed(true))
    void load()
    const id = setInterval(() => {
      if (document.visibilityState !== 'hidden') void load()
    }, REFRESH_MS)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [reloadAt])

  if (!queue) return <StaffDataState failed={failed} />

  const waiting = queue.visits.filter((v) => v.status === 'waiting').sort((a, b) => a.triage - b.triage || a.arrivedAt.localeCompare(b.arrivedAt))
  const treating = queue.visits.filter((v) => v.status === 'treating')
  const boarding = queue.visits.filter((v) => v.status === 'boarding')
  const next = waiting[0]

  async function act(visit: ErVisit, action: VisitAction) {
    setBusy(visit.id)
    setError(undefined)
    try {
      const saved = await postVisitAction(visit.id, action)
      setAnnouncement(`${visit.tag}: ${ACTION_LABEL[action].toLowerCase()}${saved.status === 'boarding' ? ', waiting for a ward bed' : ''}.`)
    } catch (err) {
      const detail = err instanceof ApiError && typeof err.body === 'object' && err.body && 'detail' in err.body ? String((err.body as { detail: string }).detail) : null
      setError(`${visit.tag}: ${detail ?? 'The hospital’s system didn’t respond. Try again.'}`)
    } finally {
      setBusy(undefined)
      setReloadAt(Date.now())
    }
  }

  const actionsFor = (visit: ErVisit) =>
    editable && visit.actions.length > 0 ? (
      <div className={bedStyles.actions}>
        {visit.actions.map((action) => (
          <button
            key={action}
            type="button"
            className={bedStyles.action}
            aria-label={`${ACTION_LABEL[action]} ${visit.tag}`}
            disabled={busy === visit.id}
            onClick={() => void act(visit, action)}
          >
            {ACTION_LABEL[action]}
          </button>
        ))}
      </div>
    ) : null

  const byTriage = [1, 2, 3, 4, 5].map((level) => ({
    level,
    count: waiting.filter((v) => v.triage === level).length,
  }))
  const today = points(arrivals.metrics, 'er.arrivals')
  const typical = typicalFor(arrivals.metrics, 'er.arrivals', today)
  const wait = points(arrivals.metrics, 'er.wait_minutes')
  const updatedAt = arrivals.metrics ? new Date(arrivals.metrics.updatedAt) : null

  return (
    <div className={pageStyles.stack}>
      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {announcement}
      </p>
      <section className={styles.lead} aria-label="The department now">
        <div className={styles.next}>
          <span className={styles.kicker}>Next to be seen</span>
          {next ? (
            <>
              <p className={styles.nextLine}>
                <strong>{next.tag}</strong> <StatusBadge tone={TRIAGE_TONE[next.triage]!}>{TRIAGE_LABEL[next.triage]}</StatusBadge>
              </p>
              <p className={styles.muted}>
                {next.complaintLabel} · {next.ageBand} · {next.sex === 'F' ? 'female' : 'male'} · waiting {minutes(next.waitedMinutes)}
              </p>
              {actionsFor(next)}
            </>
          ) : (
            <p className={styles.nextLine}>Nobody is waiting.</p>
          )}
        </div>
        <dl className={styles.figures}>
          <div>
            <dt>Waiting</dt>
            <dd>{waiting.length}</dd>
          </div>
          <div>
            <dt>Being treated</dt>
            <dd>{treating.length}</dd>
          </div>
          <div>
            <dt>Waiting for a ward bed</dt>
            <dd>{boarding.length}</dd>
          </div>
          <div>
            <dt>Emergency beds free</dt>
            <dd>
              {queue.beds.free} <span className={styles.muted}>of {queue.beds.total}</span>
            </dd>
          </div>
          <div>
            <dt>Seen in the last hour</dt>
            <dd>{queue.seenLastHour}</dd>
          </div>
        </dl>
      </section>

      <Panel title="Waiting" aside={<span className={styles.muted}>In triage order, then by arrival</span>}>
        {waiting.length === 0 ? (
          <p>Nobody is waiting to be seen.</p>
        ) : (
          <div className="table-scroll">
            <table aria-label="Waiting">
              <thead>
                <tr>
                  <th scope="col">Patient</th>
                  <th scope="col">Triage</th>
                  <th scope="col">Complaint</th>
                  <th scope="col">Age, sex</th>
                  <th scope="col">Arrived</th>
                  <th scope="col">Waiting</th>
                  {editable && <th scope="col">Next step</th>}
                </tr>
              </thead>
              <tbody>
                {waiting.map((v) => (
                  <tr key={v.id}>
                    <th scope="row">{v.tag}</th>
                    <td>
                      <StatusBadge tone={TRIAGE_TONE[v.triage]!}>{TRIAGE_LABEL[v.triage]}</StatusBadge>
                    </td>
                    <td>{v.complaintLabel}</td>
                    <td>
                      {v.ageBand}, {v.sex}
                    </td>
                    <td>{time.format(new Date(v.arrivedAt))}</td>
                    <td>{minutes(v.waitedMinutes)}</td>
                    {editable && <td>{actionsFor(v)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Being treated">
        {treating.length === 0 ? (
          <p>Nobody is being treated right now.</p>
        ) : (
          <div className="table-scroll">
            <table aria-label="Being treated">
              <thead>
                <tr>
                  <th scope="col">Patient</th>
                  <th scope="col">Triage</th>
                  <th scope="col">Complaint</th>
                  <th scope="col">Where</th>
                  <th scope="col">Seen at</th>
                  {editable && <th scope="col">Next step</th>}
                </tr>
              </thead>
              <tbody>
                {treating.map((v) => (
                  <tr key={v.id}>
                    <th scope="row">{v.tag}</th>
                    <td>
                      <StatusBadge tone={TRIAGE_TONE[v.triage]!}>{TRIAGE_LABEL[v.triage]}</StatusBadge>
                    </td>
                    <td>{v.complaintLabel}</td>
                    <td>{v.bed ?? 'Chair (fast track)'}</td>
                    <td>{v.seenAt ? time.format(new Date(v.seenAt)) : '—'}</td>
                    {editable && <td>{actionsFor(v)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {boarding.length > 0 && (
        <Panel title="Admitted, waiting for a ward bed">
          <p className={styles.muted}>Each one keeps an emergency bed until a ward bed frees up, which slows the department.</p>
          <div className="table-scroll">
            <table aria-label="Waiting for a ward bed">
              <thead>
                <tr>
                  <th scope="col">Patient</th>
                  <th scope="col">Emergency bed</th>
                  <th scope="col">Waiting since</th>
                  {editable && <th scope="col">Next step</th>}
                </tr>
              </thead>
              <tbody>
                {boarding.map((v) => (
                  <tr key={v.id}>
                    <th scope="row">{v.tag}</th>
                    <td>{v.bed ?? '—'}</td>
                    <td>{v.seenAt ? time.format(new Date(v.seenAt)) : '—'}</td>
                    {editable && <td>{actionsFor(v)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <ChartGrid>
        <ChartFrame
          title="Arrivals per hour"
          summary="Patients arriving each hour today, against a typical day (the last two weeks' average)."
          legend={[
            { label: 'Today', color: SERIES[0] },
            { label: 'Typical day', color: 'var(--ink-muted)', mark: 'band' },
          ]}
          table={{ columns: ['Hour', 'Today', 'Typical'], rows: tableRows('hour', [today, typical]) }}
          updatedAt={updatedAt}
          state={frameState(arrivals, today)}
        >
          <TimeSeriesChart
            label="Arrivals per hour today against a typical day"
            unit="hour"
            valueSuffix="patients"
            series={[{ key: 'today', label: 'Today', color: SERIES[0], points: today }]}
            band={{ label: 'Typical', points: typical }}
          />
        </ChartFrame>
        <ChartFrame
          title="Estimated wait"
          summary="The wait a new patient of middling priority could expect, over the last 24 hours."
          legend={[{ label: 'Estimated wait', color: SERIES[1] }]}
          table={{ columns: ['Hour', 'Minutes'], rows: tableRows('hour', [wait]) }}
          updatedAt={updatedAt}
          state={frameState(arrivals, wait)}
        >
          <TimeSeriesChart
            label="Estimated wait over 24 hours"
            unit="hour"
            valueSuffix="min"
            series={[{ key: 'wait', label: 'Wait', color: SERIES[1], points: wait }]}
            threshold={{ value: 60, label: 'Very busy from an hour' }}
          />
        </ChartFrame>
        <ChartFrame
          title="Waiting by triage level"
          summary="Patients waiting now, by how urgent they are."
          table={{ columns: ['Triage level', 'Waiting'], rows: byTriage.map((t) => [TRIAGE_LABEL[t.level as 1], t.count]) }}
        >
          <BarChart
            label="Waiting by triage level"
            bars={byTriage.map((t) => ({
              label: TRIAGE_LABEL[t.level as 1],
              segments: [{ key: 'n', label: 'Waiting', value: t.count, color: SERIES[0] }],
            }))}
          />
        </ChartFrame>
      </ChartGrid>

      <DepartmentStatusPanel />
    </div>
  )
}
