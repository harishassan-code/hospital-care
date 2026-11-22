import { useEffect, useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { getHospitals, type Hospital } from '../../api/hospitals'
import { exportReport, getReport, type Report, type ReportFilters, type ReportFormat } from '../../api/reports'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import formStyles from '../../components/form/Form.module.css'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import tableStyles from '../../features/hospitals/Hospitals.module.css'
import { componentLabel, formatDay, formatMinutes } from '../../features/reports/reports'
import { saveFile } from '../../lib/download'
import styles from './ReportsPage.module.css'
import pageStyles from './StaffPages.module.css'

const NO_RESPONSE = 'The hospital’s system didn’t respond, so the report couldn’t be loaded. Try again.'
const NOT_SAVED = 'The file wasn’t downloaded, because the hospital’s system didn’t respond. Try again.'

/** The server's `detail` for a 400, or the fallback when there is none. */
function detailOf(error: ApiError, fallback: string): string {
  const body = error.body
  const detail = typeof body === 'object' && body !== null && 'detail' in body ? body.detail : undefined
  return typeof detail === 'string' ? detail : fallback
}

function failure(error: unknown, action: 'read' | 'export'): string {
  if (!(error instanceof ApiError)) return action === 'read' ? NO_RESPONSE : NOT_SAVED
  if (error.status === 403) return `Your role can’t ${action === 'read' ? 'see' : 'export'} reports.`
  if (error.status === 400) return detailOf(error, 'Check the dates and try again.')
  return action === 'read' ? NO_RESPONSE : NOT_SAVED
}

const EMPTY: ReportFilters = { from: '', to: '', hospital: '' }

/**
 * Operational reports (B18, #66, #67): management (the admin role) picks a date range and, optionally, one
 * hospital, and sees requests, fulfilment time and blood wastage, with CSV and PDF downloads of the same report.
 * With no dates the server shows the last 30 days, and the date fields fill in with them.
 */
export default function ReportsPage() {
  const [draft, setDraft] = useState<ReportFilters>(EMPTY)
  const [applied, setApplied] = useState<ReportFilters>(EMPTY)
  const [report, setReport] = useState<Report>()
  const [hospitals, setHospitals] = useState<Hospital[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [exporting, setExporting] = useState<ReportFormat>()

  useEffect(() => {
    let active = true
    getHospitals()
      .then((list) => active && setHospitals(list))
      .catch(() => undefined) // the filter falls back to "All hospitals"; the report itself still loads
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    getReport(applied)
      .then((next) => {
        if (!active) return
        setReport(next)
        setError('')
        // Show the range the server used, so the fields and the files agree with the figures.
        setDraft((current) => ({ ...current, from: next.range.from, to: next.range.to }))
      })
      .catch((problem: unknown) => {
        if (!active) return
        setReport(undefined)
        setError(failure(problem, 'read'))
      })
    return () => {
      active = false
    }
  }, [applied])

  const set = (key: keyof ReportFilters) => (value: string) => setDraft((current) => ({ ...current, [key]: value }))

  function show(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setNotice('')
    setApplied({ ...draft })
  }

  /** Exports exactly the report on screen: its range as the server reported it, and its hospital. */
  async function download(format: ReportFormat) {
    if (!report) return
    setExporting(format)
    setError('')
    setNotice('')
    try {
      const { blob, filename } = await exportReport({ from: report.range.from, to: report.range.to, hospital: report.hospital ? String(report.hospital.id) : '' }, format)
      saveFile(blob, filename)
      setNotice(`Downloaded ${filename}.`)
    } catch (problem) {
      setError(failure(problem, 'export'))
    } finally {
      setExporting(undefined)
    }
  }

  return (
    <div className={pageStyles.stack}>
      <Panel title="Report period">
        <form className={styles.filters} onSubmit={show} aria-label="Report period">
          <TextField id="report-from" type="date" label="From" hint="A whole day, Karachi time" value={draft.from} onChange={set('from')} />
          <TextField id="report-to" type="date" label="To" hint="Includes that whole day. At most 366 days." value={draft.to} onChange={set('to')} />
          <Field id="report-hospital" label="Hospital">
            <select id="report-hospital" className={formStyles.input} value={draft.hospital} onChange={(e) => set('hospital')(e.target.value)}>
              <option value="">All hospitals</option>
              {hospitals.map((h) => (
                <option key={h.id} value={String(h.id)}>
                  {h.name}
                </option>
              ))}
            </select>
          </Field>
          <div className={styles.actions}>
            <Button>Show report</Button>
          </div>
        </form>
      </Panel>

      <FormAlert>{error || undefined}</FormAlert>
      {!report && !error && <p role="status">Loading…</p>}

      {report && (
        <>
          <div className={styles.toolbar}>
            <p>
              <strong>
                {formatDay(report.range.from)} to {formatDay(report.range.to)}
              </strong>{' '}
              ({report.range.days} days) · {report.hospital?.name ?? 'All hospitals'}
            </p>
            <div className={styles.downloads}>
              <Button type="button" pending={exporting === 'csv'} pendingLabel="Exporting…" disabled={exporting !== undefined} onClick={() => download('csv')}>
                Export CSV
              </Button>
              <Button type="button" pending={exporting === 'pdf'} pendingLabel="Exporting…" disabled={exporting !== undefined} onClick={() => download('pdf')}>
                Export PDF
              </Button>
            </div>
          </div>
          <p role="status">{notice}</p>

          <Panel title="Requests">
            <p className={pageStyles.note}>
              {report.requests.total} case{report.requests.total === 1 ? '' : 's'} opened in the period ·{' '}
              {report.requests.allocations} resource{report.requests.allocations === 1 ? '' : 's'} allocated.
            </p>
            <div className={styles.pair}>
              <CountTable label="Cases by severity" heading="Severity" rows={report.requests.bySeverity} />
              <CountTable label="Cases by current status" heading="Status" rows={report.requests.byStatus.filter((r) => r.count > 0)} empty="No cases opened." />
            </div>
            <div className="table-scroll">
              <table className={tableStyles.table} aria-label="Requests by resource type">
                <thead>
                  <tr>
                    <th scope="col">Resource type</th>
                    <th scope="col">Needs</th>
                    <th scope="col">Units asked</th>
                    <th scope="col">Units allocated</th>
                  </tr>
                </thead>
                <tbody>
                  {report.requests.byResourceType.map((row) => (
                    <tr key={row.id}>
                      <th scope="row">{row.label}</th>
                      <td>{row.needs}</td>
                      <td>{row.unitsAsked}</td>
                      <td>{row.unitsAllocated}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Fulfilment time">
            <p className={pageStyles.note}>From opening a case to the first time it was fulfilled, for cases fulfilled in the period.</p>
            <div className="table-scroll">
              <table className={tableStyles.table} aria-label="Fulfilment time">
                <thead>
                  <tr>
                    <th scope="col">Severity</th>
                    <th scope="col">Cases</th>
                    <th scope="col">Median</th>
                    <th scope="col">Average</th>
                    <th scope="col">90th percentile</th>
                  </tr>
                </thead>
                <tbody>
                  {[{ id: 'all', label: 'All', ...report.fulfilment.overall }, ...report.fulfilment.bySeverity].map((row) => (
                    <tr key={row.id}>
                      <th scope="row">{row.label}</th>
                      <td>{row.count}</td>
                      <td>{formatMinutes(row.medianMinutes)}</td>
                      <td>{formatMinutes(row.averageMinutes)}</td>
                      <td>{formatMinutes(row.p90Minutes)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <CountTable label="Opened in the period and never fulfilled" heading="Current status" rows={report.fulfilment.notFulfilled} empty="Every case opened in the period was fulfilled." />
          </Panel>

          <Panel title="Blood wastage">
            <p className={pageStyles.note}>
              {report.wastage.expired} unit{report.wastage.expired === 1 ? '' : 's'} expired unused · {report.wastage.discarded} discarded. Expired
              units count on their expiry date; discarded units on the day they were discarded.
            </p>
            {report.wastage.rows.length === 0 ? (
              <p>No blood was wasted in this period.</p>
            ) : (
              <div className="table-scroll">
                <table className={tableStyles.table} aria-label="Blood wastage">
                  <thead>
                    <tr>
                      <th scope="col">Hospital</th>
                      <th scope="col">Group</th>
                      <th scope="col">Component</th>
                      <th scope="col">Expired</th>
                      <th scope="col">Discarded</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.wastage.rows.map((row) => (
                      <tr key={`${row.hospital}-${row.group}-${row.component}`}>
                        <td>{row.hospital || 'No hospital'}</td>
                        <td>{row.group}</td>
                        <td>{componentLabel(row.component)}</td>
                        <td>{row.expired}</td>
                        <td>{row.discarded}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      )}
    </div>
  )
}

function CountTable({ label, heading, rows, empty }: { label: string; heading: string; rows: { id: string; label: string; count: number }[]; empty?: string }) {
  if (rows.length === 0) return <p>{empty}</p>
  return (
    <div className="table-scroll">
      <table className={tableStyles.table} aria-label={label}>
        <thead>
          <tr>
            <th scope="col">{heading}</th>
            <th scope="col">Cases</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <th scope="row">{row.label}</th>
              <td>{row.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
