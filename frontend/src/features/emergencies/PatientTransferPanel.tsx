import { useState, type FormEvent } from 'react'
import { MAX_NOTE, patientTransferAction, requestPatientTransfer, type PatientTransfer } from '../../api/emergencies'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { formatClock, formatShortDate } from '../../lib/time'
import styles from './Emergencies.module.css'
import { patientTransferFailure } from './emergencies'

type Hospital = { id: number; name: string }

/**
 * "Transfer patient" to one hospital from the sources list (story #64): an optional note, then the request. The page
 * reads the case again once it is asked for, so the other hospitals' buttons go while one is on its way.
 */
export function TransferPatientForm({
  reference,
  destination,
  onRequested,
  onCancel,
}: {
  reference: string
  destination: Hospital
  onRequested: (message: string) => void
  onCancel: () => void
}) {
  const [note, setNote] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string>()

  async function request(event: FormEvent) {
    event.preventDefault()
    if (note.trim().length > MAX_NOTE) {
      setError(`The note is too long: use at most ${MAX_NOTE} characters.`)
      return
    }
    setError(undefined)
    setPending(true)
    try {
      await requestPatientTransfer(reference, destination.id, note.trim())
      onRequested(`Patient transfer to ${destination.name} requested.`)
    } catch (failure) {
      setError(patientTransferFailure(failure))
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={request} noValidate className={styles.reserve} aria-label={`Transfer patient to ${destination.name}`}>
      <FormAlert>{error}</FormAlert>
      <TextField
        id={`patient-note-${destination.id}`}
        label="Note"
        optional
        hint={`Why the patient is moving, up to ${MAX_NOTE} characters.`}
        value={note}
        onChange={setNote}
      />
      <div className={styles.moves}>
        <button type="submit" className={styles.secondaryAction} disabled={pending} aria-busy={pending}>
          {pending ? 'Requesting…' : `Transfer patient to ${destination.name}`}
        </button>
        <button type="button" className={styles.secondaryAction} disabled={pending} onClick={onCancel}>
          Close
        </button>
      </div>
    </form>
  )
}

/** The "Transfer patient" button for one hospital; it opens the form below the row. Shown only where the server allows it. */
export function TransferPatientAction({
  reference,
  hospital,
  onRequested,
}: {
  reference: string
  hospital: Hospital
  onRequested: (message: string) => void
}) {
  const [open, setOpen] = useState(false)
  if (!open) {
    return (
      <button
        type="button"
        className={styles.secondaryAction}
        aria-label={`Transfer patient to ${hospital.name}`}
        onClick={() => setOpen(true)}
      >
        Transfer patient
      </button>
    )
  }
  return (
    <TransferPatientForm
      reference={reference}
      destination={hospital}
      onRequested={onRequested}
      onCancel={() => setOpen(false)}
    />
  )
}

/**
 * The patient transfer for this case (B17): where the patient is going, who asked and when, and, for the sending
 * hospital, a cancel with its reason. Until the receiving hospital confirms arrival, the case stays here. `transfer` is
 * the one on its way, if any; `notice` is what the page last did, shown even once that transfer is over.
 */
export function PatientTransferPanel({
  transfer,
  notice,
  onChanged,
}: {
  transfer: PatientTransfer | undefined
  notice: string
  onChanged: (message: string) => void
}) {
  const [cancelling, setCancelling] = useState(false)
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string>()

  async function cancel(event: FormEvent) {
    event.preventDefault()
    if (!transfer) return
    const text = reason.trim()
    if (!text) {
      setError('Say why the transfer is cancelled.')
      return
    }
    if (text.length > MAX_NOTE) {
      setError(`The reason is too long: use at most ${MAX_NOTE} characters.`)
      return
    }
    setError(undefined)
    setPending(true)
    try {
      await patientTransferAction(transfer.id, 'cancel', text)
      setReason('')
      setCancelling(false)
      onChanged(`Transfer to ${transfer.to.name} cancelled.`)
    } catch (failure) {
      setError(patientTransferFailure(failure))
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title="Patient transfer" id="patient-transfer">
      <p role="status">{notice}</p>
      {transfer && (
        <>
          <FormAlert>{error}</FormAlert>
          <p>
            Moving to <strong>{transfer.to.name}</strong>, asked for by {transfer.requestedBy}{' '}
            <time dateTime={transfer.requestedAt}>
              {formatShortDate(new Date(transfer.requestedAt))}, {formatClock(new Date(transfer.requestedAt))}
            </time>
            .
          </p>
          {transfer.note && <p className={styles.entryNote}>{transfer.note}</p>}
          <p className={styles.hint}>The receiving hospital confirms arrival. Until then the case stays here.</p>
          {transfer.actions.includes('cancel') &&
            (cancelling ? (
              <form onSubmit={cancel} noValidate className={styles.outcomeForm} aria-label="Cancel patient transfer">
                <TextField
                  id="patient-transfer-reason"
                  label="Reason"
                  required
                  hint={`Why the transfer is cancelled, up to ${MAX_NOTE} characters.`}
                  value={reason}
                  onChange={setReason}
                />
                <div className={styles.moves}>
                  <button type="submit" className={styles.secondaryAction} disabled={pending} aria-busy={pending}>
                    {pending ? 'Cancelling…' : 'Confirm cancellation'}
                  </button>
                  <button
                    type="button"
                    className={styles.secondaryAction}
                    disabled={pending}
                    onClick={() => {
                      setCancelling(false)
                      setError(undefined)
                    }}
                  >
                    Keep transfer
                  </button>
                </div>
              </form>
            ) : (
              <div className={styles.moves}>
                <button type="button" className={styles.secondaryAction} onClick={() => setCancelling(true)}>
                  Cancel transfer
                </button>
              </div>
            ))}
        </>
      )}
    </Panel>
  )
}
