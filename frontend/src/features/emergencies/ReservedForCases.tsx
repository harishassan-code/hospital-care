import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { allocateReservation, allocateReservations, getHeldReservations, SEVERITIES, type HeldReservation } from '../../api/emergencies'
import { FormAlert } from '../../components/form/FormAlert'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatClock } from '../../lib/time'
import { useLoad } from '../../lib/useLoad'
import styles from './Emergencies.module.css'
import { groupHeld, SEVERITY_TONE, withMinus } from './emergencies'

const loadHeldBlood = () => getHeldReservations('blood')

/** Why an allocation didn't happen: the server's words for a 403 or 409, or a plain failure. */
function failureText(error: unknown): string {
  if (error instanceof ApiError && error.status !== 0 && error.status < 500) {
    const detail = typeof error.body === 'object' && error.body !== null ? (error.body as { detail?: unknown }).detail : undefined
    return typeof detail === 'string' ? detail : 'Nothing changed. Reload the page and try again.'
  }
  return 'The hospital’s system didn’t respond, so nothing changed. Try again.'
}

/**
 * The blood held for cases at this hospital (story #46), most urgent case first, grouped by case and then by need.
 * Blood-bank staff allocate a unit, or every unit held for a need, after a confirm. `onAllocated` lets the page refresh
 * the stock figures, which the allocation changes.
 */
export function ReservedForCases({ onAllocated }: { onAllocated: () => void }) {
  const { result, setData } = useLoad(loadHeldBlood)
  const [error, setError] = useState<string>()
  const [notice, setNotice] = useState('')
  const [working, setWorking] = useState<string>()

  async function run(key: string, question: string, done: string, send: () => Promise<unknown>) {
    if (!window.confirm(question)) return
    setError(undefined)
    setNotice('')
    setWorking(key)
    try {
      await send()
      setNotice(done)
      onAllocated()
      const fresh = await getHeldReservations('blood').catch(() => null)
      if (fresh) setData(() => fresh)
    } catch (failure) {
      setError(failureText(failure))
    } finally {
      setWorking(undefined)
    }
  }

  const holds = result.state === 'ready' ? result.data : []
  return (
    <Panel title="Reserved for cases" id="reserved-for-cases">
      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {notice}
      </p>
      {result.state === 'loading' && <p role="status">Loading…</p>}
      {result.state === 'failed' && <p role="status">The reserved units couldn’t be loaded. Reload the page to try again.</p>}
      {result.state === 'ready' && holds.length === 0 && <p>No units are reserved for cases right now.</p>}
      {groupHeld(holds).map(({ case: kase, needs }) => (
        <section key={kase.reference} className={styles.source} aria-label={kase.reference}>
          <h3 className={styles.sourceHeading}>
            <Link to={`/staff/emergencies/${encodeURIComponent(kase.reference)}`}>{kase.reference}</Link>{' '}
            <StatusBadge tone={SEVERITY_TONE[kase.severity]}>{SEVERITIES.find((s) => s.id === kase.severity)?.label}</StatusBadge>
          </h3>
          {needs.map(({ need, holds: needHolds }) => {
            const label = withMinus(need.label)
            const allocatable = needHolds.filter((hold: HeldReservation) => hold.canAllocate)
            const all = `all-${need.itemId}`
            return (
              <div key={need.itemId} className={styles.source}>
                <p className={styles.candidateTop}>
                  <strong>{label}</strong>
                  <span className={styles.hint}>{need.remaining} remaining</span>
                  {allocatable.length > 1 && (
                    <button
                      type="button"
                      className={styles.secondaryAction}
                      disabled={working !== undefined}
                      aria-busy={working === all}
                      aria-label={`Allocate all ${allocatable.length} ${label} to ${kase.reference}`}
                      onClick={() =>
                        run(
                          all,
                          `Allocate all ${allocatable.length} ${label} to ${kase.reference}?`,
                          `Allocated ${allocatable.length} ${label} to ${kase.reference}.`,
                          () => allocateReservations(allocatable.map((hold: HeldReservation) => hold.id)),
                        )
                      }
                    >
                      {working === all ? 'Allocating…' : `Allocate all ${allocatable.length}`}
                    </button>
                  )}
                </p>
                <ul className={styles.candidates}>
                  {needHolds.map((hold: HeldReservation) => {
                    const unit = withMinus(hold.resource)
                    const key = `hold-${hold.id}`
                    return (
                      <li key={hold.id} className={styles.candidate}>
                        <div className={styles.candidateTop}>
                          <strong>{unit}</strong>
                          <span>
                            Holds until <time dateTime={hold.expiresAt}>{formatClock(new Date(hold.expiresAt))}</time>
                          </span>
                          {hold.canAllocate && (
                            <button
                              type="button"
                              className={styles.secondaryAction}
                              disabled={working !== undefined}
                              aria-busy={working === key}
                              aria-label={`Allocate ${unit}`}
                              onClick={() =>
                                run(key, `Allocate ${unit} to ${kase.reference}?`, `Allocated ${unit} to ${kase.reference}.`, () =>
                                  allocateReservation(hold.id),
                                )
                              }
                            >
                              {working === key ? 'Allocating…' : 'Allocate'}
                            </button>
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ul>
              </div>
            )
          })}
        </section>
      ))}
    </Panel>
  )
}
