import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  TRIP_ACTION_LABEL,
  TRIP_STATUS_LABEL,
  dispatchTransferTrip,
  getAmbulances,
  postTripAction,
  type TripAction,
} from '../../api/ambulances'
import { TRANSFER_ACTION_LABEL, TRANSFER_STATUS_LABEL, type Transfer, type TransferAction, type TransferDirection } from '../../api/transfers'
import { TextField } from '../../components/form/TextField'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { withMinus } from '../emergencies/emergencies'
import { formatClock, formatShortDate } from '../../lib/time'
import { describeTransferMove, TRANSFER_TONE } from './transfers'
import styles from './Transfers.module.css'

/** The two moves that ask for a reason first: a rejection needs one, a cancellation may have one. */
type ReasonAction = Extract<TransferAction, 'reject' | 'cancel'>

const isReasonAction = (action: TransferAction): action is ReasonAction => action === 'reject' || action === 'cancel'

const REJECT_REASON_REQUIRED = 'Say why this request is rejected.'

type CardProps = {
  transfer: Transfer
  direction: TransferDirection
  /** True while any move is being saved: every button waits. */
  busy: boolean
  /** Move the transfer; the page saves it and shows the server's copy. */
  onAction: (transfer: Transfer, action: TransferAction, extra?: { reason?: string }) => void
  /** After a trip-related update, replace the card with the server copy. */
  onTripUpdate?: (transfer: Transfer) => void
  /** Put focus on the heading, so keyboard users land on the card after a move that replaced its buttons. */
  focus: boolean
}

/**
 * One transfer (stories #47 to #49): its case, need, the other hospital, the quantities, its status in words, its history,
 * and the moves the server allows the user now, as buttons. Reject and cancel ask for a reason first; confirming receipt
 * asks first too.
 */
export function TransferCard({ transfer, direction, busy, onAction, onTripUpdate, focus }: CardProps) {
  const [reasonFor, setReasonFor] = useState<ReasonAction>()
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState<string>()
  const [ambulanceId, setAmbulanceId] = useState<number>()
  const [ambulanceOptions, setAmbulanceOptions] = useState<{ id: number; label: string }[]>([])
  const headingRef = useRef<HTMLHeadingElement>(null)
  const headingId = `transfer-${transfer.id}-title`
  const incoming = direction === 'incoming'
  const asked = new Date(transfer.createdAt)
  // Confirming receipt belongs to the outgoing transfer the user's hospital asked for. An admin is offered it on any card.
  const moves = transfer.actions.filter((action) => action !== 'deliver' || !incoming)

  useEffect(() => {
    if (focus) headingRef.current?.focus()
  }, [focus])

  useEffect(() => {
    if (!incoming || transfer.status !== 'approved' || transfer.actions.includes('dispatch') === false) return
    let alive = true
    getAmbulances()
      .then((items) => {
        if (!alive) return
        setAmbulanceOptions(
          items.filter((a) => a.status === 'available').map((a) => ({ id: a.id, label: `${a.identifier} (${a.type})` })),
        )
        if (items.some((a) => a.status === 'available')) setAmbulanceId(items.find((a) => a.status === 'available')!.id)
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [incoming, transfer.status, transfer.actions])

  function openReason(action: ReasonAction) {
    setReason('')
    setReasonError(undefined)
    setReasonFor(action)
  }

  async function dispatchAmbulance() {
    if (ambulanceId === undefined || !onTripUpdate) return
    try {
      const updated = await dispatchTransferTrip(transfer.id, ambulanceId)
      onTripUpdate(updated)
    } catch {
      /* parent shows errors via transferFailure on normal actions; trip errors surface as 409 detail */
    }
  }

  async function tripAction(action: TripAction) {
    if (!transfer.trip || !onTripUpdate) return
    const updated = await postTripAction(transfer.trip.id, action)
    onTripUpdate(updated)
  }

  function perform(action: TransferAction) {
    if (action === 'deliver' && !window.confirm(`Confirm that ${withMinus(transfer.need)} for ${transfer.case.reference} has arrived? It will be allocated to the case.`)) {
      return
    }
    onAction(transfer, action)
  }

  function submitReason(event: FormEvent, action: ReasonAction) {
    event.preventDefault()
    const text = reason.trim()
    if (action === 'reject' && !text) {
      setReasonError(REJECT_REASON_REQUIRED)
      return
    }
    onAction(transfer, action, text ? { reason: text } : {})
  }

  return (
    <article className={styles.card} aria-labelledby={headingId}>
      <header className={styles.cardHead}>
        <h3 id={headingId} ref={headingRef} tabIndex={-1} className={styles.cardTitle}>
          Transfer #{transfer.id}
        </h3>
        <StatusBadge tone={TRANSFER_TONE[transfer.status]}>{TRANSFER_STATUS_LABEL[transfer.status]}</StatusBadge>
      </header>

      <dl className={styles.facts}>
        <dt>Case</dt>
        <dd>
          {incoming ? (
            transfer.case.reference
          ) : (
            <Link to={`/staff/emergencies/${encodeURIComponent(transfer.case.reference)}`} className={styles.link}>
              {transfer.case.reference}
            </Link>
          )}
        </dd>
        <dt>Need</dt>
        <dd>{withMinus(transfer.need)}</dd>
        <dt>{incoming ? 'Asking hospital' : 'Supplying hospital'}</dt>
        <dd>{incoming ? transfer.receiver.name : transfer.supplier.name}</dd>
        <dt>Quantity</dt>
        <dd>
          <span>{transfer.quantity} requested</span>
          {transfer.approved > 0 && (
            <>
              {' · '}
              <span>{`${transfer.approved} of ${transfer.quantity} approved`}</span>
            </>
          )}
        </dd>
        <dt>Units set aside</dt>
        <dd>
          {transfer.resources.length > 0 ? (
            <ul className={styles.units}>
              {transfer.resources.map((resource) => (
                <li key={resource}>{withMinus(resource)}</li>
              ))}
            </ul>
          ) : (
            'None yet'
          )}
        </dd>
        {transfer.reason && (
          <>
            <dt>Reason</dt>
            <dd>{transfer.reason}</dd>
          </>
        )}
        <dt>Asked</dt>
        <dd>
          <time dateTime={transfer.createdAt}>
            {formatShortDate(asked)}, {formatClock(asked)}
          </time>
          {transfer.requestedBy && ` by ${transfer.requestedBy}`}
        </dd>
      </dl>

      {transfer.trip && (
        <div className={styles.trip}>
          <p>
            Ambulance <strong>{transfer.trip.ambulance.identifier}</strong> · {TRIP_STATUS_LABEL[transfer.trip.status]}
            {transfer.trip.etaMinutes != null && transfer.trip.status === 'dispatched' && (
              <> · about {transfer.trip.etaMinutes} min</>
            )}
          </p>
          {transfer.trip.actions.length > 0 && (
            <div className={styles.actions}>
              {transfer.trip.actions.map((action) => (
                <button
                  key={action}
                  type="button"
                  className={styles.button}
                  disabled={busy}
                  onClick={() => tripAction(action)}
                >
                  {TRIP_ACTION_LABEL[action]}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {incoming && transfer.status === 'approved' && transfer.actions.includes('dispatch') && !transfer.trip && ambulanceOptions.length > 0 && (
        <div className={styles.trip}>
          <label htmlFor={`transfer-${transfer.id}-ambulance`}>Dispatch ambulance</label>
          <select
            id={`transfer-${transfer.id}-ambulance`}
            className={styles.select}
            value={ambulanceId ?? ''}
            onChange={(e) => setAmbulanceId(Number(e.target.value))}
          >
            {ambulanceOptions.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
          <div className={styles.actions}>
            <button type="button" className={styles.button} disabled={busy || ambulanceId === undefined} onClick={dispatchAmbulance}>
              Dispatch ambulance
            </button>
          </div>
        </div>
      )}

      <details className={styles.history}>
        <summary>History</summary>
        <ol className={styles.timeline}>
          {transfer.history.map((entry, index) => {
            const at = new Date(entry.at)
            return (
              <li key={`${index}-${entry.at}`}>
                <strong>{describeTransferMove(entry)}</strong>
                <span className={styles.hint}>
                  <time dateTime={entry.at}>
                    {formatShortDate(at)}, {formatClock(at)}
                  </time>
                  {' · '}
                  {entry.actor ?? 'System'}
                </span>
                {entry.note && <p className={styles.entryNote}>{entry.note}</p>}
              </li>
            )
          })}
        </ol>
      </details>

      {reasonFor ? (
        <form onSubmit={(event) => submitReason(event, reasonFor)} noValidate className={styles.reason} aria-label={`Reason for transfer #${transfer.id}`}>
          <TextField
            id={`transfer-${transfer.id}-reason`}
            label="Reason"
            required={reasonFor === 'reject'}
            optional={reasonFor === 'cancel'}
            hint={reasonFor === 'reject' ? 'Tell the requesting hospital why. Required.' : 'Tell the other hospital why, if it helps.'}
            value={reason}
            onChange={(value) => {
              setReason(value)
              setReasonError(undefined)
            }}
            error={reasonError}
          />
          <div className={styles.actions}>
            <button type="submit" className={styles.button} disabled={busy} aria-busy={busy}>
              {reasonFor === 'reject' ? 'Reject request' : 'Cancel transfer'}
            </button>
            <button type="button" className={styles.button} disabled={busy} onClick={() => setReasonFor(undefined)}>
              Back
            </button>
          </div>
        </form>
      ) : moves.length > 0 ? (
        <div className={styles.actions}>
          {moves.map((action) => (
            <button
              key={action}
              type="button"
              className={styles.button}
              disabled={busy}
              aria-label={`${TRANSFER_ACTION_LABEL[action]} (transfer #${transfer.id})`}
              onClick={() => (isReasonAction(action) ? openReason(action) : perform(action))}
            >
              {TRANSFER_ACTION_LABEL[action]}
            </button>
          ))}
        </div>
      ) : (
        <p className={styles.hint}>No moves for you on this transfer.</p>
      )}
    </article>
  )
}
