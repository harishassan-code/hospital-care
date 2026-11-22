import { useCallback, useState, type FormEvent } from 'react'
import { auditExportUrl, getAudit, type AuditFilters } from '../../api/audit'
import { Button } from '../../components/form/Button'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import formStyles from '../../features/blood/Blood.module.css'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

/** Audit search and CSV export for administrators (story #56). */
export default function AuditPage() {
  const [draft, setDraft] = useState<AuditFilters>({})
  const [filters, setFilters] = useState<AuditFilters>({})
  const [page, setPage] = useState(1)
  const set = (key: keyof AuditFilters) => (value: string) => setDraft((d) => ({ ...d, [key]: value }))
  const search = (event: FormEvent) => {
    event.preventDefault()
    setFilters(draft)
    setPage(1)
  }

  return (
    <div className={pageStyles.stack}>
      <Panel title="Search the audit log">
        <form className={formStyles.form} onSubmit={search}>
          <TextField id="actor" label="Actor email" optional value={draft.actor ?? ''} onChange={set('actor')} />
          <TextField
            id="action"
            label="Action"
            optional
            hint="Exact, or a prefix ending in a dot, e.g. transfer."
            value={draft.action ?? ''}
            onChange={set('action')}
          />
          <TextField id="targetType" label="Entity" optional hint="e.g. transfers.transfer" value={draft.targetType ?? ''} onChange={set('targetType')} />
          <TextField id="from" label="From" type="date" optional value={draft.from ?? ''} onChange={set('from')} />
          <TextField id="to" label="To" type="date" optional value={draft.to ?? ''} onChange={set('to')} />
          <TextField id="q" label="Text" optional value={draft.q ?? ''} onChange={set('q')} />
          <div className={formStyles.formActions}>
            <Button>Search</Button>
            <a className={formStyles.more} href={auditExportUrl(filters)} download>
              Export CSV
            </a>
          </div>
        </form>
      </Panel>
      <Results key={`${JSON.stringify(filters)}-${page}`} filters={filters} page={page} onPage={setPage} />
    </div>
  )
}

function Results({ filters, page, onPage }: { filters: AuditFilters; page: number; onPage: (p: number) => void }) {
  const load = useCallback(() => getAudit(filters, page), [filters, page])
  const { result } = useLoad(load)
  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />
  const { count, pageSize, results } = result.data
  const pages = Math.max(1, Math.ceil(count / pageSize))

  return (
    <Panel title={`${count} ${count === 1 ? 'entry' : 'entries'}`}>
      <div className="table-scroll">
        <table aria-label="Audit entries">
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">Who</th>
              <th scope="col">Action</th>
              <th scope="col">Entity</th>
              <th scope="col">Reason</th>
              <th scope="col">Change</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.at).toLocaleString()}</td>
                <td>{r.actor}</td>
                <th scope="row">{r.action}</th>
                <td>{r.target}</td>
                <td>{r.reason || '—'}</td>
                <td>
                  {r.before || r.after ? (
                    <details>
                      <summary>Before / after</summary>
                      <pre>{JSON.stringify({ before: r.before, after: r.after }, null, 2)}</pre>
                    </details>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={pageStyles.toolbar}>
        <button type="button" className={formStyles.more} disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <span>
          Page {page} of {pages}
        </span>
        <button type="button" className={formStyles.more} disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </div>
    </Panel>
  )
}
