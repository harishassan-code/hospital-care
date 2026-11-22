import { AMBULANCE_TYPES } from '../../api/ambulances'
import { TRIP_ACTION_LABEL, TRIP_STATUS_LABEL, type Trip, type TripAction } from '../../api/trips'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatClock, formatShortDate } from '../../lib/time'
import styles from './Transfers.module.css'

type TripProps = {
  trip: Trip
  /** True while any move is being saved: every step button waits. */
  busy: boolean
  /** Make one step of the trip. The page saves it and refreshes the transfer. */
  onStep: (action: TripAction) => void
}

/** A moment as "18 Nov, 09:40", for a trip step's time. */
const when = (iso: string) => `${formatShortDate(new Date(iso))}, ${formatClock(new Date(iso))}`

/**
 * The ambulance carrying a transfer (story #51): its identifier and type, the trip's status, the estimate, the time of
 * each step, and the steps the user may take now as buttons.
 */
export function TripPanel({ trip, busy, onStep }: TripProps) {
  const type = AMBULANCE_TYPES.find((t) => t.value === trip.ambulance.type)?.label ?? trip.ambulance.type
  const steps: [string, string | null][] = [
    ['Dispatched', trip.dispatchedAt],
    ['Departed', trip.departedAt],
    ['Arrived', trip.arrivedAt],
    ['Completed', trip.completedAt],
  ]
  return (
    <section className={styles.trip} aria-label={`Trip for transfer #${trip.transferId}`}>
      <div className={styles.cardHead}>
        <h4 className={styles.tripTitle}>Ambulance {trip.ambulance.identifier}</h4>
        <StatusBadge tone="neutral">{TRIP_STATUS_LABEL[trip.status]}</StatusBadge>
      </div>
      <dl className={styles.facts}>
        <dt>Vehicle</dt>
        <dd>{type}</dd>
        <dt>Estimated trip</dt>
        <dd>about {trip.etaMinutes} min</dd>
        <dt>Dispatched by</dt>
        <dd>{trip.dispatchedBy}</dd>
      </dl>
      <ol className={styles.timeline}>
        {steps.map(([label, at]) =>
          at ? (
            <li key={label}>
              <strong>{label}</strong>
              <span className={styles.hint}>
                {' · '}
                <time dateTime={at}>{when(at)}</time>
              </span>
            </li>
          ) : (
            <li key={label} className={styles.hint}>
              {label}: not yet
            </li>
          ),
        )}
      </ol>
      {trip.actions.length > 0 && (
        <div className={styles.actions}>
          {trip.actions.map((action) => (
            <button
              key={action}
              type="button"
              className={styles.button}
              disabled={busy}
              aria-label={`${TRIP_ACTION_LABEL[action]} (transfer #${trip.transferId})`}
              onClick={() => onStep(action)}
            >
              {TRIP_ACTION_LABEL[action]}
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
