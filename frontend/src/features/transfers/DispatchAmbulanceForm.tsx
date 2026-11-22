import { useCallback, useState, type FormEvent } from 'react'
import { AMBULANCE_TYPES, getAmbulances, type Ambulance } from '../../api/ambulances'
import type { Transfer } from '../../api/transfers'
import { Field } from '../../components/form/Field'
import { useLoad } from '../../lib/useLoad'
import styles from './Transfers.module.css'

type DispatchProps = {
  transfer: Transfer
  /** Send the chosen ambulance. Resolves true when it was sent, and the form closes. The page shows any refusal. */
  onDispatch: (ambulanceId: number) => Promise<boolean>
  onClose: () => void
}

const typeLabel = (type: Ambulance['type']) => AMBULANCE_TYPES.find((t) => t.value === type)?.label ?? type

/**
 * Choose an available ambulance at the supplying hospital to carry an approved transfer (story #51). The ETA is the
 * supplier-to-receiver estimate, fixed when the ambulance is sent.
 */
export function DispatchAmbulanceForm({ transfer, onDispatch, onClose }: DispatchProps) {
  const supplierId = transfer.supplier.id
  const load = useCallback(() => getAmbulances({ status: 'available', hospitalId: supplierId }), [supplierId])
  const { result } = useLoad(load)
  const [chosen, setChosen] = useState('')
  const [error, setError] = useState<string>()
  const [pending, setPending] = useState(false)

  if (result.state === 'loading') return <p className={styles.hint}>Looking for available ambulances…</p>
  if (result.state === 'failed') {
    return (
      <div className={styles.reason}>
        <p>The ambulances at {transfer.supplier.name} couldn’t be loaded. Try again.</p>
        <div className={styles.actions}>
          <button type="button" className={styles.button} onClick={onClose}>
            Back
          </button>
        </div>
      </div>
    )
  }

  const vehicles = result.data
  if (vehicles.length === 0) {
    return (
      <div className={styles.reason}>
        <p>No ambulance is available at {transfer.supplier.name} right now.</p>
        <div className={styles.actions}>
          <button type="button" className={styles.button} onClick={onClose}>
            Back
          </button>
        </div>
      </div>
    )
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!chosen) {
      setError('Choose an ambulance.')
      return
    }
    setPending(true)
    const sent = await onDispatch(Number(chosen))
    setPending(false)
    if (sent) onClose()
  }

  return (
    <form onSubmit={submit} noValidate className={styles.reason} aria-label={`Dispatch an ambulance for transfer #${transfer.id}`}>
      <Field
        id={`transfer-${transfer.id}-ambulance`}
        label="Ambulance"
        error={error}
        hint={`Available at ${transfer.supplier.name}. Estimated trip to ${transfer.receiver.name}: about ${transfer.etaMinutes} min.`}
      >
        <select
          id={`transfer-${transfer.id}-ambulance`}
          className={styles.select}
          value={chosen}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `transfer-${transfer.id}-ambulance-error` : `transfer-${transfer.id}-ambulance-hint`}
          onChange={(event) => {
            setChosen(event.target.value)
            setError(undefined)
          }}
        >
          <option value="">Choose an ambulance</option>
          {vehicles.map((vehicle) => (
            <option key={vehicle.id} value={vehicle.id}>
              {vehicle.identifier} · {typeLabel(vehicle.type)}
            </option>
          ))}
        </select>
      </Field>
      <div className={styles.actions}>
        <button type="submit" className={styles.button} disabled={pending} aria-busy={pending} aria-label={`Dispatch ambulance (transfer #${transfer.id})`}>
          {pending ? 'Dispatching…' : 'Dispatch'}
        </button>
        <button type="button" className={styles.button} disabled={pending} onClick={onClose}>
          Back
        </button>
      </div>
    </form>
  )
}
