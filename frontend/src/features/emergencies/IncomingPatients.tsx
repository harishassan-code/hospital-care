import { useCallback, useState } from 'react'
import { getPatientTransfers, patientTransferAction, SEVERITIES, type PatientTransfer, type PatientTransferStatus } from '../../api/emergencies'
import { FormAlert } from '../../components/form/FormAlert'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge, type Tone } from '../../components/ui/StatusBadge'
import { formatClock, formatShortDate } from '../../lib/time'
import { useLoad } from '../../lib/useLoad'
import { describePatientTransfer, patientTransferFailure, SEVERITY_TONE, withMinus } from './emergencies'
import styles from './Emergencies.module.css'

/** How a patient transfer's status reads in the outgoing list. */
const STATUS_WORD: Record<PatientTransferStatus, string> = {
  requested: 'Requested',
  arrived: 'Arrived',
  cancelled: 'Cancelled',
}
const STATUS_TONE: Record<PatientTransferStatus, Tone> = { requested: 'neutral', arrived: 'ok', cancelled: 'neutral' }

/**
 * Patients on their way to this hospital (B17, story #65): the moves other hospitals have asked for and that haven't
 * arrived. Before arrival the case itself isn't readable here, so each row shows only what the transfer carries. Confirming
 * arrival moves the case to this hospital, and its list then has it.
 */
export function IncomingPatients() {
  const load = useCallback(() => getPatientTransfers('incoming', 'requested'), [])
  const { result, setData } = useLoad(load)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState<string>()
  const [working, setWorking] = useState<number>()

  async function arrive(transfer: PatientTransfer) {
    setError(undefined)
    setNotice('')
    setWorking(transfer.id)
    try {
      const arrived = await patientTransferAction(transfer.id, 'arrive')
      setData((current) => current.filter((row) => row.id !== arrived.id))
      setNotice(`${arrived.reference} has arrived. It is on this hospital’s list now.`)
    } catch (failure) {
      setError(patientTransferFailure(failure))
    } finally {
      setWorking(undefined)
    }
  }

  return (
    <Panel title="Incoming patients" id="incoming-patients">
      <FormAlert>{error}</FormAlert>
      {notice && <p role="status">{notice}</p>}
      {result.state === 'loading' && <p role="status">Looking for incoming patients…</p>}
      {result.state === 'failed' && <p role="status">The list didn’t load. Reload the page to try again.</p>}
      {result.state === 'ready' &&
        (result.data.length === 0 ? (
          <p>No patients are on their way here.</p>
        ) : (
          <ul className={styles.candidates}>
            {result.data.map((transfer) => (
              <IncomingRow
                key={transfer.id}
                transfer={transfer}
                working={working === transfer.id}
                disabled={working !== undefined}
                onArrive={() => arrive(transfer)}
              />
            ))}
          </ul>
        ))}
    </Panel>
  )
}

function IncomingRow({
  transfer,
  working,
  disabled,
  onArrive,
}: {
  transfer: PatientTransfer
  working: boolean
  disabled: boolean
  onArrive: () => void
}) {
  const requested = new Date(transfer.requestedAt)
  const severity = SEVERITIES.find((s) => s.id === transfer.severity)?.label
  return (
    <li className={styles.candidate}>
      <div className={styles.candidateTop}>
        <strong>{transfer.reference}</strong>
        {transfer.patientRef && <span>Patient {transfer.patientRef}</span>}
        <StatusBadge tone={SEVERITY_TONE[transfer.severity]}>{severity}</StatusBadge>
      </div>
      <div>
        <span>{transfer.needs.map(withMinus).join(', ')}</span>
        {' · '}
        <span>From {transfer.from.name}</span>
        {' · '}
        <span>
          Requested{' '}
          <time dateTime={transfer.requestedAt}>
            {formatShortDate(requested)}, {formatClock(requested)}
          </time>
        </span>
      </div>
      {transfer.note && <p className={styles.entryNote}>{transfer.note}</p>}
      {transfer.actions.includes('arrive') && (
        <div className={styles.moves}>
          <button
            type="button"
            className={styles.secondaryAction}
            disabled={disabled}
            aria-busy={working}
            aria-label={`Confirm arrival of ${transfer.reference}`}
            onClick={onArrive}
          >
            {working ? 'Confirming…' : 'Confirm arrival'}
          </button>
        </div>
      )}
    </li>
  )
}

/**
 * Patients this hospital is moving to another (B17): each request, and what became of it. The sending side cancels from
 * the case page. Arrival is the receiving hospital's to confirm; an admin may confirm it for them (the API lists
 * `arrive` in the row's actions), which is how the demo, with no logins at the partner hospitals, completes a move
 * (functional sweep). Once the patient arrives the case is no longer this hospital's, so there is no link.
 */
export function OutgoingPatients() {
  const load = useCallback(() => getPatientTransfers('outgoing'), [])
  const { result, setData } = useLoad(load)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState<string>()
  const [working, setWorking] = useState<number>()

  async function arrive(transfer: PatientTransfer) {
    setError(undefined)
    setNotice('')
    setWorking(transfer.id)
    try {
      const arrived = await patientTransferAction(transfer.id, 'arrive')
      setData((current) => current.map((row) => (row.id === arrived.id ? arrived : row)))
      setNotice(`${arrived.reference} has arrived at ${arrived.to.name}. The case is theirs now.`)
    } catch (failure) {
      setError(patientTransferFailure(failure))
    } finally {
      setWorking(undefined)
    }
  }

  return (
    <Panel title="Outgoing patients" id="outgoing-patients">
      <FormAlert>{error}</FormAlert>
      {notice && <p role="status">{notice}</p>}
      {result.state === 'loading' && <p role="status">Looking for outgoing patients…</p>}
      {result.state === 'failed' && <p role="status">The list didn’t load. Reload the page to try again.</p>}
      {result.state === 'ready' &&
        (result.data.length === 0 ? (
          <p>No patients are being moved from here.</p>
        ) : (
          <ul className={styles.candidates}>
            {result.data.map((transfer) => (
              <li key={transfer.id} className={styles.candidate}>
                <div className={styles.candidateTop}>
                  <strong>{transfer.reference}</strong>
                  <StatusBadge tone={STATUS_TONE[transfer.status]}>{STATUS_WORD[transfer.status]}</StatusBadge>
                </div>
                <div>{describePatientTransfer(transfer, transfer.status === 'arrived' ? 'arrived' : 'requested')}</div>
                {transfer.status === 'cancelled' && <p className={styles.entryNote}>Cancelled: {transfer.reason}</p>}
                {transfer.status === 'requested' && transfer.actions.includes('arrive') && (
                  <div className={styles.moves}>
                    <button
                      type="button"
                      className={styles.secondaryAction}
                      disabled={working !== undefined}
                      aria-busy={working === transfer.id}
                      aria-label={`Confirm arrival of ${transfer.reference} at ${transfer.to.name}`}
                      onClick={() => arrive(transfer)}
                    >
                      {working === transfer.id ? 'Confirming…' : `Confirm arrival at ${transfer.to.name}`}
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        ))}
    </Panel>
  )
}
