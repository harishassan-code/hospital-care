import { useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { getStaffing, postShiftAction, type ShiftAction, type ShiftRow, type ShiftStatus, type Staffing } from '../../api/staffing'
import { BarChart, ChartFrame, ChartGrid, SERIES, TimeSeriesChart, type Point } from '../../components/charts'
import { FormAlert } from '../../components/form/FormAlert'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge, type Tone } from '../../components/ui/StatusBadge'
import { tableRows } from '../../features/charts/useMetrics'
import bedStyles from '../../features/beds/Beds.module.css'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { StaffDataState } from './StaffDataState'
import edStyles from './EmergencyDepartmentPage.module.css'
import pageStyles from './StaffPages.module.css'

const REFRESH_MS = 60_000
const STATUS: Record<ShiftStatus, { label: string; tone: Tone }> = {
  onDuty: { label: 'On duty', tone: 'ok' },
  late: { label: 'On duty, came in late', tone: 'warning' },
  notInYet: { label: 'Not in yet', tone: 'warning' },
  missing: { label: 'Missing', tone: 'critical' },
  absent: { label: 'Absent', tone: 'critical' },
  upcoming: { label: 'Starts soon', tone: 'neutral' },
  finished: { label: 'Gone home', tone: 'neutral' },
}
const ACTION_LABEL: Record<ShiftAction, string> = { clockIn: 'Clock in now', markAbsent: 'Mark absent' }
const time = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' })
const ROLE_LABEL = { doctor: 'Doctor', nurse: 'Nurse' } as const

/** Today's hours as times: each hour's middle, on the Karachi calendar of `now`. */
function hourTimes(now: string): number[] {
  const day = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Karachi' }).format(new Date(now))
  const midnight = Date.parse(`${day}T00:00:00+05:00`)
  return Array.from({ length: 24 }, (_, h) => midnight + (h * 60 + 30) * 60_000)
}

/**
 * Staff on duty (B22): who is on now against the rota, who hasn't come in, and whether any department has more
 * patients per nurse than it should. The nurse in charge (or an admin) clocks someone in or marks them absent.
 */
export default function StaffingPage() {
  const { role } = useStaff()
  const editable = canEdit(role, 'staffing')
  const [data, setData] = useState<Staffing | null>(null)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState<number>()
  const [error, setError] = useState<string>()
  const [announcement, setAnnouncement] = useState('')
  const [reloadAt, setReloadAt] = useState(0)

  useEffect(() => {
    let active = true
    const load = () =>
      getStaffing()
        .then((next) => {
          if (!active) return
          setData(next)
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

  if (!data) return <StaffDataState failed={failed} />

  async function act(row: ShiftRow, action: ShiftAction) {
    setBusy(row.id)
    setError(undefined)
    try {
      await postShiftAction(row.id, action)
      setAnnouncement(`${row.name}: ${action === 'clockIn' ? 'clocked in' : 'marked absent'}.`)
    } catch (err) {
      setError(`${row.name}: ${err instanceof ApiError && err.status === 409 ? 'That can’t be done for this shift now.' : 'The hospital’s system didn’t respond. Try again.'}`)
    } finally {
      setBusy(undefined)
      setReloadAt(Date.now())
    }
  }

  const gaps = data.people.filter((p) => p.status === 'missing' || p.status === 'notInYet' || p.status === 'absent')
  const onNow = data.people.filter((p) => p.status !== 'upcoming')
  const short = data.ratios.filter((r) => r.short)
  const hours = hourTimes(data.now)
  const line = (pick: (d: Staffing['day'][number]) => number | undefined): Point[] =>
    data.day.flatMap((d, i) => {
      const value = pick(d)
      return value === undefined ? [] : [{ t: hours[i]!, value }]
    })
  const plannedNurses = line((d) => d.plannedNurses)
  const nurses = line((d) => d.nurses)
  const plannedDoctors = line((d) => d.plannedDoctors)
  const doctors = line((d) => d.doctors)

  const actions = (row: ShiftRow) =>
    editable && row.actions.length > 0 ? (
      <div className={bedStyles.actions}>
        {row.actions.map((action) => (
          <button
            key={action}
            type="button"
            className={bedStyles.action}
            aria-label={`${ACTION_LABEL[action]}: ${row.name}`}
            disabled={busy === row.id}
            onClick={() => void act(row, action)}
          >
            {ACTION_LABEL[action]}
          </button>
        ))}
      </div>
    ) : null

  return (
    <div className={pageStyles.stack}>
      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {announcement}
      </p>
      <section className={edStyles.lead} aria-label="On duty now">
        <div className={edStyles.next}>
          <span className={edStyles.kicker}>Needs cover</span>
          <p className={edStyles.nextLine}>
            {gaps.length === 0 && short.length === 0
              ? 'Everyone due is in, and no department is short.'
              : `${gaps.length} not in · ${short.length} ${short.length === 1 ? 'department' : 'departments'} short of nurses`}
          </p>
        </div>
        <dl className={edStyles.figures}>
          {(['doctor', 'nurse'] as const).map((r) => (
            <div key={r}>
              <dt>{ROLE_LABEL[r]}s on duty</dt>
              <dd>
                {data.summary[r].onDuty} <span className={edStyles.muted}>of {data.summary[r].planned}</span>
              </dd>
            </div>
          ))}
          <div>
            <dt>Missing or absent</dt>
            <dd>{data.summary.doctor.missing + data.summary.nurse.missing}</dd>
          </div>
        </dl>
      </section>

      <Panel title="Not in" aside={<span className={edStyles.muted}>Due now, not clocked in</span>}>
        {gaps.length === 0 ? (
          <p>Everyone due on this shift has clocked in.</p>
        ) : (
          <div className="table-scroll">
            <table aria-label="Not in">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Role</th>
                  <th scope="col">Department</th>
                  <th scope="col">Shift</th>
                  <th scope="col">Status</th>
                  {editable && <th scope="col">Action</th>}
                </tr>
              </thead>
              <tbody>
                {gaps.map((p) => (
                  <tr key={p.id}>
                    <th scope="row">{p.name}</th>
                    <td>{ROLE_LABEL[p.role]}</td>
                    <td>{p.department}</td>
                    <td>
                      {time.format(new Date(p.startsAt))}–{time.format(new Date(p.endsAt))}
                    </td>
                    <td>
                      <StatusBadge tone={STATUS[p.status].tone}>{STATUS[p.status].label}</StatusBadge>
                    </td>
                    {editable && <td>{actions(p)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <ChartGrid>
        <ChartFrame
          title="Patients per nurse"
          summary="Patients in each department's beds for every nurse on duty there, against the most it should have."
          table={{
            columns: ['Department', 'Patients', 'Nurses on duty', 'Patients per nurse', 'At most'],
            rows: data.ratios.map((r) => [r.department, r.patients, r.nurses, r.patientsPerNurse ?? 'no nurse', r.target]),
          }}
        >
          <BarChart
            label="Patients per nurse by department"
            thresholds={data.ratios.map((r) => r.target)}
            max={Math.max(10, ...data.ratios.map((r) => Math.max(r.target, r.patientsPerNurse ?? 0)))}
            bars={data.ratios.map((r) => ({
              label: r.department,
              segments: [{ key: 'ratio', label: 'Patients per nurse', value: r.patientsPerNurse ?? 0, color: SERIES[0] }],
              note: r.patientsPerNurse === null ? 'no nurse' : `${r.patientsPerNurse} (at most ${r.target})`,
              flag: r.short ? 'Short' : undefined,
            }))}
          />
        </ChartFrame>
        <ChartFrame
          title="On duty through the day"
          summary="Doctors and nurses clocked in each hour today, against the rota (dashed)."
          legend={[
            { label: 'Nurses', color: SERIES[0] },
            { label: 'Nurses planned', color: SERIES[0], mark: 'dashed' },
            { label: 'Doctors', color: SERIES[1] },
            { label: 'Doctors planned', color: SERIES[1], mark: 'dashed' },
          ]}
          table={{
            columns: ['Hour', 'Nurses', 'Nurses planned', 'Doctors', 'Doctors planned'],
            rows: tableRows('hour', [nurses, plannedNurses, doctors, plannedDoctors]),
          }}
        >
          <TimeSeriesChart
            label="Staff on duty today against the rota"
            unit="hour"
            series={[
              { key: 'nurses', label: 'Nurses', color: SERIES[0], points: nurses },
              { key: 'pn', label: 'Nurses planned', color: SERIES[0], points: plannedNurses, dashed: true },
              { key: 'doctors', label: 'Doctors', color: SERIES[1], points: doctors },
              { key: 'pd', label: 'Doctors planned', color: SERIES[1], points: plannedDoctors, dashed: true },
            ]}
          />
        </ChartFrame>
      </ChartGrid>

      <Panel title="On this shift">
        <div className="table-scroll">
          <table aria-label="On this shift">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Role</th>
                <th scope="col">Department</th>
                <th scope="col">Shift</th>
                <th scope="col">Clocked in</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {onNow.map((p) => (
                <tr key={p.id}>
                  <th scope="row">{p.name}</th>
                  <td>{ROLE_LABEL[p.role]}</td>
                  <td>{p.department}</td>
                  <td>
                    {time.format(new Date(p.startsAt))}–{time.format(new Date(p.endsAt))}
                  </td>
                  <td>{p.clockedInAt ? time.format(new Date(p.clockedInAt)) : '—'}</td>
                  <td>
                    <StatusBadge tone={STATUS[p.status].tone}>{STATUS[p.status].label}</StatusBadge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}
