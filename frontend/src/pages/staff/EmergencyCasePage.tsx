import { useCallback, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import {
  allocateReservation,
  getCandidates,
  getCase,
  MAX_NOTE,
  postCaseAction,
  releaseReservation,
  reserveStock,
  SEVERITIES,
  type AvailableNeed,
  type Candidate,
  type CandidateItem,
  type CaseAction,
  type CaseAllocation,
  type CaseReservation,
  type EmergencyCaseDetail,
  type HospitalMatch,
  type Score,
  type StatusChange,
  type UnmetNeed,
} from '../../api/emergencies'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { CaseStatusLabel } from '../../features/emergencies/CaseStatusLabel'
import {
  ACTION_LABEL,
  describeMove,
  describeNeed,
  SEVERITY_TONE,
  shortfallSummary,
  STATUS_LABEL,
  timelineOf,
  withMinus,
  type TimelineEntry,
} from '../../features/emergencies/emergencies'
import styles from '../../features/emergencies/Emergencies.module.css'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { formatClock, formatShortDate } from '../../lib/time'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

/** The server's words for a close without an outcome note (story #35). */
const OUTCOME_REQUIRED = 'Add an outcome note to close the case.'

/** One emergency case: its details, the moves its status allows, and its timeline (story #34). */
export default function EmergencyCasePage() {
  const { reference = '' } = useParams()
  return <CaseView key={reference} reference={reference} />
}

function CaseView({ reference }: { reference: string }) {
  const { role } = useStaff()
  const load = useCallback(() => getCase(reference), [reference])
  const { result, setData } = useLoad(load)
  const [notice, setNotice] = useState('')
  /** After a hold is made or released, the case is read again so its figures and holds are the server's. */
  const refreshCase = (message: string) => {
    setNotice(message)
    void getCase(reference).then((fresh) => setData(() => fresh))
  }

  if (result.state === 'failed' && result.status === 404) {
    return (
      <div className={pageStyles.stack}>
        <p role="status">No emergency case with that id.</p>
        <Link to="/staff/emergencies" className={styles.back}>
          ← All emergency cases
        </Link>
      </div>
    )
  }
  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const kase = result.data
  const opened = new Date(kase.createdAt)
  const severity = SEVERITIES.find((s) => s.id === kase.severity)?.label

  return (
    <div className={pageStyles.stack}>
      <Link to="/staff/emergencies" className={styles.back}>
        ← All emergency cases
      </Link>
      <Panel title={kase.id} id="case" aside={<StatusBadge tone={SEVERITY_TONE[kase.severity]}>{severity}</StatusBadge>}>
        <dl className={styles.facts}>
          <dt>Status</dt>
          <dd>
            <CaseStatusLabel status={kase.status} />
          </dd>
          <dt>Opened</dt>
          <dd>
            <time dateTime={kase.createdAt}>
              {formatShortDate(opened)}, {formatClock(opened)}
            </time>
            {kase.createdBy && ` by ${kase.createdBy}`}
          </dd>
          {kase.patientRef && (
            <>
              <dt>Patient ref</dt>
              <dd>{kase.patientRef}</dd>
            </>
          )}
          <dt>Needed</dt>
          <dd>
            <ul className={styles.needs}>
              {kase.items.map((need) => (
                <li key={need.itemId}>
                  <span>{describeNeed(need)}</span>{' '}
                  <span className={styles.hint}>
                    Available here: {need.localAvailable} · {need.shortfall > 0 ? `Short: ${need.shortfall}` : 'Covered locally'}
                  </span>{' '}
                  <span className={styles.hint}>
                    {need.remaining === 0
                      ? 'Fully allocated'
                      : `${need.fulfilled} of ${need.quantity} allocated · ${need.remaining} remaining`}
                  </span>
                  {canEdit(role, 'emergencies') && need.localAvailable > 0 && need.remaining > need.reserved && (
                    <ReserveHere
                      key={`${need.itemId}-${need.localAvailable}-${need.reserved}`}
                      reference={kase.id}
                      need={need}
                      onReserved={refreshCase}
                    />
                  )}
                </li>
              ))}
            </ul>
            <p className={styles.summary}>{shortfallSummary(kase.shortfallTotal)}</p>
          </dd>
        </dl>
      </Panel>

      {(kase.reservations.length > 0 || canEdit(role, 'emergencies')) && (
        <Reservations
          reference={kase.id}
          holds={kase.reservations}
          canRelease={canEdit(role, 'emergencies')}
          notice={notice}
          onChanged={refreshCase}
        />
      )}

      {kase.shortfallTotal > 0 && <Sources reference={kase.id} />}

      {kase.outcome !== null && (
        <Panel title="Outcome" id="outcome">
          <p className={styles.outcome}>{kase.outcome}</p>
        </Panel>
      )}

      {canEdit(role, 'emergencies') && <CaseMoves kase={kase} onMoved={(updated) => setData(() => updated)} />}
      <Timeline entries={timelineOf(kase.history, kase.allocations)} />
    </div>
  )
}

/** Distance and travel time as the sources lists show them: "4.2 km · ~6 min". */
function distanceText(place: { distanceKm: number | null; travelMinutes: number | null }): string {
  if (place.distanceKm === null || place.travelMinutes === null) return 'Distance unknown'
  return `${place.distanceKm.toFixed(1)} km · ~${place.travelMinutes} min`
}

/**
 * The other hospitals that can supply each short need (story #38), best first with their scores (story #41). The
 * server ranks them and this shows that order as it comes. Asked for only when the case has a shortfall, so a case
 * covered locally makes no extra request.
 */
function Sources({ reference }: { reference: string }) {
  const load = useCallback(() => getCandidates(reference), [reference])
  const { result } = useLoad(load)
  return (
    <Panel title="Sources in the network" id="sources">
      {result.state === 'loading' && <p role="status">Looking for hospitals…</p>}
      {result.state === 'failed' && (
        <p role="status">The network didn’t answer, so the sources aren’t shown. Reload the page to try again.</p>
      )}
      {result.state === 'ready' && (
        <div className={styles.sources}>
          {result.data.items.length >= 2 && <BestDestination hospitals={result.data.hospitals} />}
          {result.data.items.map((item) => (
            <SourceItem key={item.itemId} item={item} />
          ))}
        </div>
      )}
    </Panel>
  )
}

/**
 * The hospitals judged across every short need at once (story #42), in the server's order. Shown only with two or more
 * short needs: with one, the list for that need below already answers the question.
 */
function BestDestination({ hospitals }: { hospitals: HospitalMatch[] }) {
  const anyComplete = hospitals.some((hospital) => hospital.complete)
  return (
    <section className={styles.source} aria-labelledby="best-destination">
      <h3 className={styles.sourceHeading} id="best-destination">
        Best single destination
      </h3>
      {!anyComplete && (
        <p className={styles.hint}>No single hospital has everything; split the request or use the per-need sources below.</p>
      )}
      {hospitals.length > 0 && (
        <ul className={styles.candidates}>
          {hospitals.map((hospital) => (
            <DestinationRow key={hospital.hospital.id} hospital={hospital} />
          ))}
        </ul>
      )}
    </section>
  )
}

/**
 * One hospital across the short needs: whether it has everything, how many it covers, its score and distance, and
 * what it is missing. The badges are words, not colour alone.
 */
function DestinationRow({ hospital }: { hospital: HospitalMatch }) {
  return (
    <li className={hospital.recommended ? styles.recommended : styles.candidate}>
      <div className={styles.candidateTop}>
        <span className={styles.rank}>Rank {hospital.rank}</span>
        <strong>{hospital.hospital.name}</strong>
        {hospital.complete && <span className={styles.badge}>Has everything</span>}
        {hospital.recommended && <span className={styles.badge}>Recommended</span>}
        <span className={styles.score}>{hospital.score.toFixed(1)} / 100</span>
      </div>
      <div>
        <span>{hospital.coverage} needs</span>{' · '}
        <span>{distanceText(hospital)}</span>
      </div>
      {hospital.unmet.length > 0 && <p className={styles.missing}>Missing: {hospital.unmet.map(missingText).join(', ')}</p>}
    </li>
  )
}

/** One unmet need in words: "1 × Ventilator", or "1 × O− red cells (only 1 of 2)" when the hospital has some of it. */
function missingText(need: UnmetNeed): string {
  const partial = need.available > 0 ? ` (only ${need.available} of ${need.available + need.missing})` : ''
  return `${need.missing} × ${withMinus(need.need)}${partial}`
}

/** One short need and the hospitals that have it, best first, or the empty state when none do. */
function SourceItem({ item }: { item: CandidateItem }) {
  return (
    <section className={styles.source}>
      <h3 className={styles.sourceHeading}>
        {withMinus(item.need)}: short {item.shortfall}
      </h3>
      {item.candidates.length === 0 ? (
        <p className={styles.hint}>No other hospital has this right now</p>
      ) : (
        <>
          <p className={styles.hint}>Ordered by {item.strategy.label.toLowerCase()}</p>
          <ul className={styles.candidates}>
            {item.candidates.map((candidate) => (
              <SourceRow key={candidate.hospital.id} candidate={candidate} strategyLabel={item.strategy.label} />
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

/** One hospital in a short need's list: its rank, score, stock, distance, and why it scored as it did. */
function SourceRow({ candidate, strategyLabel }: { candidate: Candidate; strategyLabel: string }) {
  return (
    <li className={candidate.recommended ? styles.recommended : styles.candidate}>
      <div className={styles.candidateTop}>
        <span className={styles.rank}>Rank {candidate.rank}</span>
        <strong>{candidate.hospital.name}</strong>
        {candidate.recommended && <span className={styles.badge}>Recommended</span>}
        <span className={styles.score}>{candidate.score.total.toFixed(1)} / 100</span>
      </div>
      <div>
        <span>{candidate.available} available</span>{' · '}
        <span className={styles.marker}>{candidate.covers ? 'covers it' : 'partial'}</span>{' · '}
        <span>{distanceText(candidate)}</span>
      </div>
      {candidate.earliestExpiry && (
        <span className={styles.hint}>
          Earliest expiry <time dateTime={candidate.earliestExpiry}>{formatShortDate(new Date(candidate.earliestExpiry))}</time>
        </span>
      )}
      <ScoreBreakdown score={candidate.score} strategyLabel={strategyLabel} />
    </li>
  )
}

/** "Why this score?": each factor's label, reason and points, then the total the points add up to (story #41). */
function ScoreBreakdown({ score, strategyLabel }: { score: Score; strategyLabel: string }) {
  return (
    <details className={styles.why}>
      <summary>Why this score?</summary>
      <p className={styles.hint}>Strategy: {strategyLabel}</p>
      <ul className={styles.factors}>
        {score.factors.map((factor) => (
          <li key={factor.name}>
            <strong>{factor.label}</strong>: {factor.detail} <span className={styles.points}>{factor.points.toFixed(1)} points</span>
          </li>
        ))}
        <li className={styles.factorTotal}>
          Total <span className={styles.points}>{score.total.toFixed(1)} of 100</span>
        </li>
      </ul>
    </details>
  )
}

/**
 * "Reserve N here" for one need (story #43): how many of this hospital's stock to hold for the case. It starts at the
 * smaller of what is free here and what the need still lacks. The server has the last word on both.
 */
function ReserveHere({
  reference,
  need,
  onReserved,
}: {
  reference: string
  need: AvailableNeed
  onReserved: (message: string) => void
}) {
  const remaining = need.remaining - need.reserved
  const [count, setCount] = useState(String(Math.min(need.localAvailable, remaining)))
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string>()
  const asked = Number(count)
  const valid = Number.isInteger(asked) && asked >= 1 && asked <= remaining

  async function reserve(event: FormEvent) {
    event.preventDefault()
    if (!valid) {
      setError(`Enter a whole number from 1 to ${remaining}.`)
      return
    }
    setError(undefined)
    setPending(true)
    try {
      const holds = await reserveStock(reference, need.itemId, asked)
      onReserved(`Reserved here: ${holds.map((hold) => withMinus(hold.resource)).join(', ')}.`)
    } catch (failure) {
      setError(reservationFailure(failure))
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={reserve} noValidate className={styles.reserve} aria-label="Reserve stock here">
      <FormAlert>{error}</FormAlert>
      <TextField
        id={`reserve-${need.itemId}`}
        label="How many"
        type="number"
        inputMode="numeric"
        min={1}
        max={remaining}
        value={count}
        onChange={setCount}
      />
      <button type="submit" className={styles.secondaryAction} disabled={pending} aria-busy={pending}>
        {pending ? 'Reserving…' : valid ? `Reserve ${asked} here` : 'Reserve here'}
      </button>
    </form>
  )
}

/**
 * The stock held for this case (story #43): what each hold is, until when it is held and at which hospital, with a
 * release for each one still held. Staff who can't edit see the list without the buttons. The words, not colour, say
 * what each hold is.
 */
function Reservations({
  reference,
  holds,
  canRelease,
  notice,
  onChanged,
}: {
  reference: string
  holds: CaseReservation[]
  canRelease: boolean
  notice: string
  onChanged: (message: string) => void
}) {
  const [working, setWorking] = useState<{ id: number; kind: 'release' | 'allocate' }>()
  const [error, setError] = useState<string>()

  async function release(hold: CaseReservation) {
    setError(undefined)
    setWorking({ id: hold.id, kind: 'release' })
    try {
      const released = await releaseReservation(reference, hold.id)
      onChanged(`Released ${withMinus(released.resource)}.`)
    } catch (failure) {
      setError(reservationFailure(failure))
    } finally {
      setWorking(undefined)
    }
  }

  /** Confirm, then hand the held resource over to this case (story #46). The case is read again on success. */
  async function allocate(hold: CaseReservation) {
    const name = withMinus(hold.resource)
    if (!window.confirm(`Allocate ${name} to ${reference}? This confirms it for the case.`)) return
    setError(undefined)
    setWorking({ id: hold.id, kind: 'allocate' })
    try {
      await allocateReservation(hold.id)
      onChanged(`Allocated ${name}.`)
    } catch (failure) {
      setError(reservationFailure(failure))
    } finally {
      setWorking(undefined)
    }
  }

  return (
    <Panel title="Reservations" id="reservations">
      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {notice}
      </p>
      {holds.length === 0 ? (
        <p>Nothing is held for this case.</p>
      ) : (
        <ul className={styles.candidates}>
          {holds.map((hold) => (
            <li key={hold.id} className={styles.candidate}>
              <div className={styles.candidateTop}>
                <strong>{withMinus(hold.resource)}</strong>
                <span className={styles.badge}>{hold.status === 'held' ? 'Held' : 'Allocated'}</span>
              </div>
              <div>
                {hold.status === 'held' ? (
                  <span>
                    Holds until <time dateTime={hold.expiresAt}>{formatClock(new Date(hold.expiresAt))}</time>
                  </span>
                ) : (
                  <span>Confirmed for this case</span>
                )}{' '}
                · <span>{hold.hospital.name}</span> · <span>reserved by {hold.reservedBy}</span>
              </div>
              {((canRelease && hold.status === 'held') || hold.canAllocate) && (
                <div className={styles.moves}>
                  {hold.canAllocate && (
                    <button
                      type="button"
                      className={styles.secondaryAction}
                      disabled={working !== undefined}
                      aria-busy={working?.id === hold.id && working.kind === 'allocate'}
                      aria-label={`Allocate ${withMinus(hold.resource)}`}
                      onClick={() => allocate(hold)}
                    >
                      {working?.id === hold.id && working.kind === 'allocate' ? 'Allocating…' : 'Allocate'}
                    </button>
                  )}
                  {canRelease && hold.status === 'held' && (
                    <button
                      type="button"
                      className={styles.secondaryAction}
                      disabled={working !== undefined}
                      aria-busy={working?.id === hold.id && working.kind === 'release'}
                      aria-label={`Release ${withMinus(hold.resource)}`}
                      onClick={() => release(hold)}
                    >
                      {working?.id === hold.id && working.kind === 'release' ? 'Releasing…' : 'Release'}
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

/** Why a hold, release or allocation didn't happen: the server's words for a 400 or 409, or a plain failure. */
function reservationFailure(error: unknown): string {
  if (error instanceof ApiError && error.status !== 0 && error.status < 500) {
    const detail = typeof error.body === 'object' && error.body !== null ? (error.body as { detail?: unknown }).detail : undefined
    return typeof detail === 'string' ? detail : 'Nothing changed. Check the details and try again.'
  }
  return 'The hospital’s system didn’t respond, so nothing changed. Try again.'
}

/**
 * The moves the server says are valid from the current status, each with an optional note. Closing opens an
 * outcome form first: the note is required (story #35).
 */
function CaseMoves({ kase, onMoved }: { kase: EmergencyCaseDetail; onMoved: (updated: EmergencyCaseDetail) => void }) {
  const [note, setNote] = useState('')
  const [pending, setPending] = useState<CaseAction>()
  const [error, setError] = useState<string>()
  const [announcement, setAnnouncement] = useState('')
  const [closing, setClosing] = useState(false)
  const [outcome, setOutcome] = useState('')
  const [outcomeError, setOutcomeError] = useState<string>()

  async function move(action: CaseAction) {
    if (note.trim().length > MAX_NOTE) {
      setError(`The note is too long: use at most ${MAX_NOTE} characters.`)
      return
    }
    setError(undefined)
    setAnnouncement('')
    setPending(action)
    try {
      const updated = await postCaseAction(kase.id, action, note.trim())
      setNote('')
      onMoved(updated)
      setAnnouncement(`${updated.id} is now ${STATUS_LABEL[updated.status].toLowerCase()}.`)
    } catch (failure) {
      setError(moveFailure(failure))
    } finally {
      setPending(undefined)
    }
  }

  function startClosing() {
    setError(undefined)
    setAnnouncement('')
    setClosing(true)
  }

  async function close(event: FormEvent) {
    event.preventDefault()
    const text = outcome.trim()
    if (!text) {
      setOutcomeError(OUTCOME_REQUIRED)
      return
    }
    if (text.length > MAX_NOTE) {
      setOutcomeError(`The outcome note is too long: use at most ${MAX_NOTE} characters.`)
      return
    }
    setOutcomeError(undefined)
    setError(undefined)
    setAnnouncement('')
    setPending('close')
    try {
      const updated = await postCaseAction(kase.id, 'close', text)
      setOutcome('')
      setClosing(false)
      onMoved(updated)
      setAnnouncement(`${updated.id} is now closed.`)
    } catch (failure) {
      const noteError = serverNoteError(failure)
      if (noteError) setOutcomeError(noteError)
      else setError(moveFailure(failure))
    } finally {
      setPending(undefined)
    }
  }

  return (
    <Panel title="Update status" id="moves">
      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {announcement}
      </p>
      {kase.actions.length === 0 ? (
        <p>No moves from {STATUS_LABEL[kase.status].toLowerCase()}.</p>
      ) : closing ? (
        <form onSubmit={close} className={styles.outcomeForm}>
          <TextField
            id="case-outcome"
            label="Outcome note"
            required
            hint={`How the case ended. Required to close it, up to ${MAX_NOTE} characters.`}
            value={outcome}
            onChange={setOutcome}
            error={outcomeError}
          />
          <div className={styles.moves}>
            <button type="submit" className={styles.secondaryAction} disabled={pending !== undefined} aria-busy={pending === 'close'}>
              {pending === 'close' ? 'Closing…' : 'Close case'}
            </button>
            <button
              type="button"
              className={styles.secondaryAction}
              disabled={pending !== undefined}
              onClick={() => {
                setClosing(false)
                setOutcomeError(undefined)
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <>
          <TextField
            id="move-note"
            label="Note"
            optional
            hint={`Why the status is changing, up to ${MAX_NOTE} characters.`}
            value={note}
            onChange={setNote}
          />
          <div className={styles.moves}>
            {kase.actions.map((action) => (
              <button
                key={action}
                type="button"
                className={styles.secondaryAction}
                disabled={pending !== undefined}
                aria-busy={pending === action}
                onClick={() => (action === 'close' ? startClosing() : move(action))}
              >
                {pending === action ? 'Saving…' : ACTION_LABEL[action]}
              </button>
            ))}
          </div>
        </>
      )}
    </Panel>
  )
}

/** The server's 400 on the outcome note, e.g. "Add an outcome note to close the case." Undefined for anything else. */
function serverNoteError(error: unknown): string | undefined {
  if (!(error instanceof ApiError) || error.status !== 400 || typeof error.body !== 'object' || error.body === null) return undefined
  const note = (error.body as { note?: unknown }).note
  return Array.isArray(note) && typeof note[0] === 'string' ? note[0] : undefined
}

/** Why a move didn't happen. A 409 says why in the server's words; anything else is a plain failure. */
function moveFailure(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    const detail = typeof error.body === 'object' && error.body !== null ? (error.body as { detail?: unknown }).detail : undefined
    return typeof detail === 'string' ? detail : 'That move isn’t allowed from the case’s current status. Reload to see it.'
  }
  if (error instanceof ApiError && error.status !== 0 && error.status < 500) return 'The case wasn’t changed. Check the note and try again.'
  return 'The hospital’s system didn’t respond, so the case wasn’t changed. Try again.'
}

/**
 * Every status move and every allocation (story #45), oldest first. An entry with no actor was made by the system.
 */
function Timeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <Panel title="Status history" id="history">
      {entries.length === 0 ? (
        <p>No history yet.</p>
      ) : (
        <ol className={styles.timeline}>
          {entries.map((entry) =>
            entry.kind === 'move' ? (
              <MoveEntry key={`move-${entry.at}-${entry.change.action}`} change={entry.change} />
            ) : (
              <AllocationEntry key={`allocation-${entry.allocation.id}`} allocation={entry.allocation} />
            ),
          )}
        </ol>
      )}
    </Panel>
  )
}

function MoveEntry({ change }: { change: StatusChange }) {
  const at = new Date(change.at)
  return (
    <li>
      <strong>{describeMove(change)}</strong>
      <span className={styles.hint}>
        <time dateTime={change.at}>
          {formatShortDate(at)}, {formatClock(at)}
        </time>
        {' · '}
        {change.actor ?? 'System'}
      </span>
      {change.note && <p className={styles.entryNote}>{change.note}</p>}
    </li>
  )
}

function AllocationEntry({ allocation }: { allocation: CaseAllocation }) {
  const at = new Date(allocation.at)
  return (
    <li>
      <strong>
        Allocated {withMinus(allocation.resource)} from {allocation.hospital.name} by {allocation.allocatedBy}
      </strong>
      <span className={styles.hint}>
        <time dateTime={allocation.at}>
          {formatShortDate(at)}, {formatClock(at)}
        </time>
      </span>
      {allocation.note && <p className={styles.entryNote}>{allocation.note}</p>}
    </li>
  )
}
