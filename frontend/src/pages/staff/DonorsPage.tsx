import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BLOOD_GROUPS, type BloodGroup } from '../../api/blood'
import { listDonors, type Donor } from '../../api/donors'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { Panel } from '../../components/ui/Panel'
import { formatGroup } from '../../features/blood/blood'
import { DonorPanel } from '../../features/donors/DonorPanel'
import { DonorTable } from '../../features/donors/DonorTable'
import styles from '../../features/donors/Donors.module.css'
import { RegisterDonorForm } from '../../features/donors/RegisterDonorForm'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import pageStyles from './StaffPages.module.css'

/** Wait this long after typing stops before searching. */
const SEARCH_DELAY_MS = 300
/** The most rows the API returns (DonorListView). */
const LIST_LIMIT = 200

type GroupFilter = 'all' | BloodGroup

/**
 * Donors for blood bank staff (B11): search and register donors, record screening, book and cancel donation
 * appointments. The chosen donor's code is kept in ?donor= so a reload keeps the panel open.
 */
export default function DonorsPage() {
  const { role } = useStaff()
  const [params, setParams] = useSearchParams()
  const selected = params.get('donor')
  const [typed, setTyped] = useState('')
  const [search, setSearch] = useState('')
  const [group, setGroup] = useState<GroupFilter>('all')
  const [registering, setRegistering] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [message, setMessage] = useState('')

  useEffect(() => {
    const id = setTimeout(() => setSearch(typed.trim()), SEARCH_DELAY_MS)
    return () => clearTimeout(id)
  }, [typed])

  // A new filter object is what makes the list load again. `attempt` changes it on "Try again" and after a registration.
  const filter = useMemo(
    () => ({ q: search || undefined, bloodGroup: group === 'all' ? undefined : group, attempt }),
    [search, group, attempt],
  )
  const load = useCallback(() => listDonors(filter), [filter])
  const { result, setData } = useLoad(load)

  const canWrite = canEdit(role, 'donors')
  const filtering = search !== '' || group !== 'all'
  const donors: Donor[] = result.state === 'ready' ? result.data : []

  function openDonor(code: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('donor', code)
      return next
    })
  }

  function closeDonor() {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('donor')
      return next
    })
  }

  function registered(donor: Donor) {
    setRegistering(false)
    setMessage(`Donor ${donor.id} registered.`)
    setAttempt((n) => n + 1)
    openDonor(donor.id)
  }

  /** A saved screening replaces the donor's row, so the list shows the new eligibility without a reload. */
  function changed(donor: Donor) {
    setData((list) => list.map((row) => (row.id === donor.id ? donor : row)))
  }

  return (
    <div className={pageStyles.split}>
      <div className={pageStyles.stack}>
        {registering && <RegisterDonorForm onRegistered={registered} onClose={() => setRegistering(false)} />}

        <Panel
          title="Donors"
          aside={result.state === 'ready' ? <span className={styles.note}>{donors.length} shown</span> : undefined}
        >
          <div className={pageStyles.toolbar}>
            <Field id="donor-search" label="Search donors" hint="Name, code or phone.">
              <input
                id="donor-search"
                type="search"
                className={styles.control}
                value={typed}
                autoComplete="off"
                aria-describedby="donor-search-hint"
                onChange={(e) => setTyped(e.target.value)}
              />
            </Field>
            <Field id="donor-group" label="Blood group">
              <select
                id="donor-group"
                className={styles.control}
                value={group}
                onChange={(e) => setGroup(e.target.value as GroupFilter)}
              >
                <option value="all">All groups</option>
                {BLOOD_GROUPS.map((g) => (
                  <option key={g} value={g}>
                    {formatGroup(g)}
                  </option>
                ))}
              </select>
            </Field>
            {canWrite && !registering && (
              <button type="button" className={styles.more} onClick={() => setRegistering(true)}>
                Register a donor
              </button>
            )}
          </div>

          <p role="status" className={styles.note}>
            {result.state === 'loading' ? 'Loading donors…' : message}
          </p>

          {result.state === 'failed' && (
            <>
              <p role="alert">Couldn’t load donors.</p>
              <Button type="button" onClick={() => setAttempt((n) => n + 1)}>
                Try again
              </Button>
            </>
          )}
          {result.state === 'ready' && donors.length === 0 && (
            <p>{filtering ? 'No donors match this search.' : 'No donors registered at your hospital yet.'}</p>
          )}
          {donors.length > 0 && <DonorTable donors={donors} selectedId={selected} onSelect={openDonor} />}
          {donors.length === LIST_LIMIT && (
            <p className={styles.note}>Showing the first 200 matches. Narrow the search to see the rest.</p>
          )}
        </Panel>
      </div>

      {selected && <DonorPanel key={selected} code={selected} canWrite={canWrite} onChanged={changed} onClose={closeDonor} />}
    </div>
  )
}
