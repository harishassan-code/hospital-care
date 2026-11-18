import { useState, type FormEvent } from 'react'
import type { Candidate } from '../../api/emergencies'
import { requestTransfer } from '../../api/transfers'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import styles from '../emergencies/Emergencies.module.css'
import { transferFailure } from './transfers'

type RequestProps = {
  /** The need of the case this asks for. */
  itemId: number
  /** The hospital that could supply it, from the sources list. */
  candidate: Candidate
  /** How many the need is still short here. */
  shortfall: number
  /** How many more of the need may be asked for at all (`askableFor`). The server enforces the same limit. */
  askable: number
  /** Called with the notice to show once the request is saved. The case is then read again. */
  onRequested: (message: string) => void
}

/**
 * "Request N from <hospital>" for one hospital in a short need's sources (story #47). The quantity starts at the smaller of
 * the shortfall and what that hospital has, and never more than the need can still take. The server has the last word.
 */
export function RequestTransferForm({ itemId, candidate, shortfall, askable, onRequested }: RequestProps) {
  const name = candidate.hospital.name
  const [count, setCount] = useState(String(Math.max(1, Math.min(shortfall, candidate.available, askable))))
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string>()
  const asked = Number(count)
  const valid = Number.isInteger(asked) && asked >= 1 && asked <= askable

  async function request(event: FormEvent) {
    event.preventDefault()
    if (!valid) {
      setError(`Enter a whole number from 1 to ${askable}.`)
      return
    }
    setError(undefined)
    setPending(true)
    try {
      const transfer = await requestTransfer({ itemId, supplierId: candidate.hospital.id, quantity: asked })
      onRequested(`Transfer #${transfer.id} requested: ${asked} from ${name}.`)
    } catch (failure) {
      setError(transferFailure(failure))
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={request} noValidate className={styles.reserve} aria-label={`Request transfer from ${name}`}>
      <FormAlert>{error}</FormAlert>
      <TextField
        id={`transfer-request-${itemId}-${candidate.hospital.id}`}
        label="Quantity"
        type="number"
        inputMode="numeric"
        min={1}
        max={askable}
        value={count}
        onChange={setCount}
      />
      <button type="submit" className={styles.secondaryAction} disabled={pending} aria-busy={pending}>
        {pending ? 'Requesting…' : valid ? `Request ${asked} from ${name}` : `Request from ${name}`}
      </button>
    </form>
  )
}
