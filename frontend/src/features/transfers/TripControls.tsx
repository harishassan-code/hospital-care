import { useState } from 'react'
import { dispatchTrip, getAvailableAmbulances, postTripAction, TRIP_STATUS_LABEL, type Ambulance } from '../../api/ambulances'
import { ApiError } from '../../api/client'
import type { Transfer } from '../../api/transfers'
import { FormAlert } from '../../components/form/FormAlert'
import formStyles from '../blood/Blood.module.css'

/**
 * Ambulance dispatch and trip tracking on a transfer (story #51). The supplier picks an available ambulance
 * for an approved transfer, then marks it en route and arrived; receipt (story #49) completes the trip.
 */
export function TripControls({ transfer, canTrack, onChanged }: { transfer: Transfer; canTrack: boolean; onChanged: () => void }) {
  const [fleet, setFleet] = useState<Ambulance[]>()
  const [choice, setChoice] = useState<number>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const trip = transfer.trip

  const run = async (work: () => Promise<unknown>) => {
    setBusy(true)
    setError(undefined)
    try {
      await work()
      onChanged()
    } catch (failure) {
      setError(
        failure instanceof ApiError && failure.status === 409
          ? 'That ambulance or transfer has moved on. The list now shows the latest state.'
          : failure instanceof ApiError && failure.status === 403
            ? 'Only the supplying hospital dispatches and tracks this trip.'
            : 'The hospital’s system didn’t respond. Try again.',
      )
      if (failure instanceof ApiError && failure.status === 409) onChanged()
    } finally {
      setBusy(false)
    }
  }

  if (trip) {
    const next = trip.status === 'dispatched' ? 'enRoute' : trip.status === 'enRoute' ? 'arrive' : null
    return (
      <div aria-label={`Trip for transfer ${transfer.id}`}>
        <p>
          Ambulance {trip.ambulance.identifier}: {TRIP_STATUS_LABEL[trip.status]}
          {trip.etaMinutes !== null && trip.status !== 'completed' ? ` · ETA about ${trip.etaMinutes} min` : ''}
        </p>
        {next && canTrack && (
          <button type="button" className={formStyles.more} disabled={busy} onClick={() => run(() => postTripAction(trip.id, next))}>
            {next === 'enRoute' ? 'Mark en route' : 'Mark arrived'}
          </button>
        )}
        <FormAlert>{error}</FormAlert>
      </div>
    )
  }

  if (transfer.status !== 'approved' || !transfer.actions.includes('dispatch')) return null
  if (!fleet) {
    return (
      <button
        type="button"
        className={formStyles.more}
        disabled={busy}
        onClick={() =>
          getAvailableAmbulances(transfer.supplier.id)
            .then((list) => {
              setFleet(list)
              setChoice(list[0]?.id)
            })
            .catch(() => setError('The fleet couldn’t be loaded. Try again.'))
        }
      >
        Dispatch with ambulance
      </button>
    )
  }
  return (
    <div>
      {fleet.length === 0 ? (
        <p>No ambulance is available right now.</p>
      ) : (
        <>
          <label htmlFor={`ambulance-${transfer.id}`}>Ambulance</label>{' '}
          <select id={`ambulance-${transfer.id}`} value={choice} onChange={(e) => setChoice(Number(e.target.value))}>
            {fleet.map((a) => (
              <option key={a.id} value={a.id}>
                {a.identifier} ({a.type.toUpperCase()})
              </option>
            ))}
          </select>{' '}
          <button
            type="button"
            className={formStyles.more}
            disabled={busy || choice === undefined}
            onClick={() => choice !== undefined && run(() => dispatchTrip(transfer.id, choice))}
          >
            Send ambulance
          </button>
        </>
      )}
      <FormAlert>{error}</FormAlert>
    </div>
  )
}
