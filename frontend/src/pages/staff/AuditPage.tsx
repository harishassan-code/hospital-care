import { Fragment, useEffect, useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { AUDIT_PAGE_SIZE, EMPTY_AUDIT_FILTERS, exportAuditCsv, listAuditEntries, type AuditFilters, type AuditPage } from '../../api/audit'
import { Button } from '../../components/form/Button'
import formStyles from '../../components/form/Form.module.css'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import tableStyles from '../../features/hospitals/Hospitals.module.css'
import { saveFile } from '../../lib/download'
import styles from './AuditPage.module.css'
import pageStyles from './StaffPages.module.css'

/** Times are shown in the hospital's time zone, the one the filters' days are cut in. */
const KARACHI_TIME = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Karachi',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** The server's `detail` for a 400, or the fallback when there is none. */
function detailOf(error: ApiError, fallback: string): string {
  const body = error.body
  const detail = typeof body === 'object' && body !== null && 'detail' in body ? body.detail : undefined
  return typeof detail === 'string' ? detail : fallback
}

function loadFailure(error: unknown): string {
  if (!(error instanceof ApiError)) return NO_RESPONSE
  if (error.status === 403) return 'Your role can’t read the audit trail.'
  if (error.status === 400) return detailOf(error, 'Check the filters and try again.')
  return NO_RESPONSE
}

function exportFailure(error: unknown): string {
  if (!(error instanceof ApiError)) return 'The file wasn’t downloaded, because the hospital’s system didn’t respond. Try again.'
  if (error.status === 403) return 'Your role can’t export the audit trail.'
  if (error.status === 400) return detailOf(error, 'The file wasn’t downloaded. Narrow the filters and try again.')
  return 'The file wasn’t downloaded, because the hospital’s system didn’t respond. Try again.'
}

const NO_RESPONSE = 'The hospital’s system didn’t respond, so the entries couldn’t be loaded. Try again.'

/** A before or after value as JSON text. Nothing recorded shows as "None". */
const jsonText = (value: unknown) => (value === null || value === undefined ? 'None' : JSON.stringify(value, null, 2))

/**
 * The audit trail (B10, #56): an administrator searches every critical action, opens its values and exports the
 * matches to CSV. Filters apply when Search is pressed; paging and the export use the filters on screen.
 */
export default function AuditPage() {
  const [draft, setDraft] = useState<AuditFilters>(EMPTY_AUDIT_FILTERS)
  const [applied, setApplied] = useState<AuditFilters>(EMPTY_AUDIT_FILTERS)
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<AuditPage>()
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [openId, setOpenId] = useState<number>()
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    let active = true
    listAuditEntries(applied, offset)
      .then((next) => {
        if (!active) return
        setPage(next)
        setError('')
      })
      .catch((failure: unknown) => {
        if (!active) return
        setPage(undefined)
        setError(loadFailure(failure))
      })
    return () => {
      active = false
    }
  }, [applied, offset])

  const set = (key: keyof AuditFilters) => (value: string) => setDraft((current) => ({ ...current, [key]: value }))

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setApplied(draft)
    setOffset(0)
    setOpenId(undefined)
    setNotice('')
  }

  function clear() {
    setDraft({ ...EMPTY_AUDIT_FILTERS })
    setApplied({ ...EMPTY_AUDIT_FILTERS })
    setOffset(0)
    setOpenId(undefined)
    setNotice('')
  }

  function turn(next: number) {
    setOffset(next)
    setOpenId(undefined)
  }

  async function exportCsv() {
    setExporting(true)
    setError('')
    setNotice('')
    try {
      const { blob, filename } = await exportAuditCsv(applied)
      saveFile(blob, filename)
      setNotice(`Downloaded ${filename}.`)
    } catch (failure) {
      setError(exportFailure(failure))
    } finally {
      setExporting(false)
    }
  }

  const first = offset + 1
  const last = page ? offset + page.results.length : 0

  return (
    <div className={pageStyles.stack}>
      <Panel title="Search the audit trail">
        <form className={styles.filters} onSubmit={search} aria-label="Search the audit trail">
          <TextField id="audit-actor" label="Who (email)" hint="Exact, ignoring capitals" value={draft.actor} onChange={set('actor')} autoComplete="off" />
          <TextField id="audit-action" label="Action" hint="Starts with, e.g. bed. for every bed action" value={draft.action} onChange={set('action')} autoComplete="off" />
          <TextField id="audit-type" label="Object type" hint="e.g. hospitals.hospital" value={draft.targetType} onChange={set('targetType')} autoComplete="off" />
          <TextField id="audit-object" label="Object ID" hint="Use with object type to see one object’s history" value={draft.targetId} onChange={set('targetId')} autoComplete="off" />
          <TextField id="audit-from" type="date" label="From" hint="A whole day, Karachi time" value={draft.from} onChange={set('from')} />
          <TextField id="audit-to" type="date" label="To" hint="Includes that whole day" value={draft.to} onChange={set('to')} />
          <TextField id="audit-text" label="Search text" hint="Matches who, action, object, object ID and reason" value={draft.text} onChange={set('text')} autoComplete="off" />
          <div className={styles.actions}>
            <Button>Search</Button>
            <button type="button" className={`${formStyles.button} ${formStyles.secondary}`} onClick={clear}>
              Clear filters
            </button>
          </div>
        </form>
      </Panel>

      <Panel title="Audit entries">
        <p className={pageStyles.note}>Newest first. Times are shown in Karachi time (PKT).</p>
        <div className={styles.toolbar}>
          <p role="status">{notice || (!page && !error ? 'Loading…' : '')}</p>
          <Button type="button" pending={exporting} pendingLabel="Exporting…" onClick={exportCsv}>
            Export CSV
          </Button>
        </div>
        <FormAlert>{error || undefined}</FormAlert>

        {page && page.count === 0 && <p>No audit entries match these filters.</p>}
        {page && page.count > 0 && (
          <>
            <div className="table-scroll">
              <table className={tableStyles.table} aria-label="Audit entries">
                <thead>
                  <tr>
                    <th scope="col">When</th>
                    <th scope="col">Who</th>
                    <th scope="col">Action</th>
                    <th scope="col">Object</th>
                    <th scope="col">Reason</th>
                    <th scope="col">Values</th>
                  </tr>
                </thead>
                <tbody>
                  {page.results.map((entry) => {
                    const open = openId === entry.id
                    return (
                      <Fragment key={entry.id}>
                        <tr>
                          <td>{KARACHI_TIME.format(new Date(entry.at))}</td>
                          <td>{entry.actorEmail || 'System'}</td>
                          <td>
                            <code>{entry.action}</code>
                          </td>
                          <td>
                            {entry.targetRepr}
                            <span className={styles.muted}>
                              <br />
                              {entry.targetType} · {entry.targetId}
                            </span>
                          </td>
                          <td>{entry.reason || '—'}</td>
                          <td>
                            <button
                              type="button"
                              className={styles.control}
                              aria-expanded={open}
                              aria-controls={`audit-values-${entry.id}`}
                              aria-label={`${open ? 'Hide' : 'Show'} values of entry ${entry.id}`}
                              onClick={() => setOpenId(open ? undefined : entry.id)}
                            >
                              {open ? 'Hide' : 'Show'}
                            </button>
                          </td>
                        </tr>
                        {open && (
                          <tr id={`audit-values-${entry.id}`}>
                            <td colSpan={6}>
                              <div className={styles.values}>
                                <section>
                                  <h3>Before</h3>
                                  <pre>{jsonText(entry.before)}</pre>
                                </section>
                                <section>
                                  <h3>After</h3>
                                  <pre>{jsonText(entry.after)}</pre>
                                </section>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <nav className={styles.pager} aria-label="Pages of audit entries">
              <button type="button" className={styles.control} disabled={offset === 0} onClick={() => turn(Math.max(0, offset - AUDIT_PAGE_SIZE))}>
                Previous
              </button>
              <p>
                {first.toLocaleString('en-US')}–{last.toLocaleString('en-US')} of {page.count.toLocaleString('en-US')}
              </p>
              <button
                type="button"
                className={styles.control}
                disabled={offset + page.results.length >= page.count}
                onClick={() => turn(offset + AUDIT_PAGE_SIZE)}
              >
                Next
              </button>
            </nav>
          </>
        )}
      </Panel>
    </div>
  )
}
