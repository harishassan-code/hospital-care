import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { TRANSFER_ACTION_LABEL, TRANSFER_STATUS_LABEL, type Transfer, type TransferAction, type TransferDirection, type TransferMove } from '../../api/transfers'
import type { Trip, TripAction } from '../../api/trips'
import { TextField } from '../../components/form/TextField'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { withMinus } from '../emergencies/emergencies'
import { formatClock, formatShortDate } from '../../lib/time'
import { DispatchAmbulanceForm } from './DispatchAmbulanceForm'
import { describeTransferMove, TRANSFER_TONE } from './transfers'
import { TripPanel } from './TripPanel'
import styles from './Transfers.module.css'

/** The two moves that ask for a reason first: a rejection needs one, a cancellation may have one. */
type ReasonAction = Extract<TransferAction, 'reject' | 'cancel'>

const isReasonAction = (action: TransferMove): action is ReasonAction => action === 'reject' || action === 'cancel'

const REJECT_REASON_REQUIRED = 'Say why this request is rejected.'

type CardProps = {
  transfer: Transfer
  direction: TransferDirection
  /** True while any move is being saved: every button waits. */
  busy: boolean
  /** Move the transfer; the page saves it and shows the server's copy. */
  onAction: (transfer: Transfer, action: TransferAction, extra?: { reason?: string }) => void
  /** Send an available ambulance to carry the transfer. Resolves true when it was sent. */
  onDispatch: (transfer: Transfer, ambulanceId: number) => Promise<boolean>
  /** Make one step of the transfer's trip. */
  onTripStep: (transfer: Transfer, trip: Trip, action: TripAction) => void
  /** Put focus on the heading, so keyboard users land on the card after a move that replaced its buttons. */
  focus: boolean
}

/**
 * One transfer (stories #47 to #49): its case, need, the other hospital, the quantities, its status in words, its history,
 * and the moves the server allows the user now, as buttons. Reject and cancel ask for a reason first; confirming receipt
 * asks first too.
 */
export function TransferCard({ transfer, direction, busy, onAction, onDispatch, onTripStep, focus }: CardProps) {
  const [reasonFor, setReasonFor] = useState<ReasonAction>()
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState<string>()
  const [dispatching, setDispatching] = useState(false)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const headingId = `transfer-${transfer.id}-title`
  const incoming = direction === 'incoming'
  const trip = transfer.trip
  const asked = new Date(transfer.createdAt)
  // Confirming receipt belongs to the outgoing transfer the user's hospital asked for. An admin is offered it on any card.
  const moves = transfer.actions.filter((action) => action !== 'deliver' || !incoming)

  useEffect(() => {
    if (focus) headingRef.current?.focus()
  }, [focus])

  function openReason(action: ReasonAction) {
    setReason('')
    setReasonError(undefined)
    setReasonFor(action)
  }

  function perform(action: TransferAction) {
    if (action === 'deliver' && !window.confirm(`Confirm that ${withMinus(transfer.need)} for ${transfer.case.reference} has arrived? It will be allocated to the case.`)) {
      return
    }
    onAction(transfer, action)
  }

  /** One of the card's buttons: dispatching opens the ambulance choice, a reason is asked first, the rest act now. */
  function choose(action: TransferMove) {
    if (action === 'dispatchAmbulance') {
      setDispatching(true)
    } else if (isReasonAction(action)) {
      openReason(action)
    } else {
      perform(action)
    }
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

      {trip && <TripPanel trip={trip} busy={busy} onStep={(action) => onTripStep(transfer, trip, action)} />}

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
      ) : dispatching ? (
        <DispatchAmbulanceForm
          transfer={transfer}
          onDispatch={(ambulanceId) => onDispatch(transfer, ambulanceId)}
          onClose={() => setDispatching(false)}
        />
      ) : moves.length > 0 ? (
        <div className={styles.actions}>
          {moves.map((action) => (
            <button
              key={action}
              type="button"
              className={styles.button}
              disabled={busy}
              aria-label={`${TRANSFER_ACTION_LABEL[action]} (transfer #${transfer.id})`}
              onClick={() => choose(action)}
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
