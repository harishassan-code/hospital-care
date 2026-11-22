import { useCallback, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import {
  listTransfers,
  postTransferAction,
  TRANSFER_STATUS_LABEL,
  type Transfer,
  type TransferAction,
  type TransferDirection,
  type TransferStatus,
} from '../../api/transfers'
import { dispatchAmbulance, postTripAction, TRIP_STATUS_LABEL, type Trip, type TripAction } from '../../api/trips'
import { FormAlert } from '../../components/form/FormAlert'
import { Panel } from '../../components/ui/Panel'
import { TransferCard } from '../../features/transfers/TransferCard'
import { transferFailure } from '../../features/transfers/transfers'
import styles from '../../features/transfers/Transfers.module.css'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

type StatusFilter = 'all' | TransferStatus

/** The lifecycle's order, for the status filter. */
const STATUSES: readonly TransferStatus[] = ['requested', 'approved', 'dispatched', 'inTransit', 'delivered', 'rejected', 'cancelled']

const TABS: readonly { id: TransferDirection; label: string }[] = [
  { id: 'incoming', label: 'Incoming' },
  { id: 'outgoing', label: 'Outgoing' },
]

const HEADING: Record<TransferDirection, string> = {
  incoming: 'Asked of this hospital',
  outgoing: 'Asked of other hospitals',
}

/**
 * Transfers of stock between hospitals (stories #47 to #49). Incoming: other hospitals asking this one to supply. Outgoing:
 * this hospital asking another. The tabs are links, so the page's address says which one is open.
 */
export default function TransfersPage() {
  const [params] = useSearchParams()
  const direction: TransferDirection = params.get('direction') === 'outgoing' ? 'outgoing' : 'incoming'
  const [status, setStatus] = useState<StatusFilter>('all')

  return (
    <div className={pageStyles.stack}>
      <nav aria-label="Transfer direction">
        <ul className={styles.tabList}>
          {TABS.map((tab) => (
            <li key={tab.id}>
              <Link
                to={{ pathname: '/staff/transfers', search: `?direction=${tab.id}` }}
                className={styles.tab}
                aria-current={tab.id === direction ? 'page' : undefined}
              >
                {tab.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <Panel title={HEADING[direction]} id="transfers">
        <div className={pageStyles.toolbar}>
          <div className={styles.filter}>
            <label htmlFor="transfer-status">Status</label>
            <select id="transfer-status" className={styles.select} value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)}>
              <option value="all">All</option>
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {TRANSFER_STATUS_LABEL[value]}
                </option>
              ))}
            </select>
          </div>
        </div>
        <TransferList key={`${direction}:${status}`} direction={direction} status={status} />
      </Panel>
    </div>
  )
}

/** The transfers for one direction and status: the loading and failed states, the empty states, and a card for each. */
function TransferList({ direction, status }: { direction: TransferDirection; status: StatusFilter }) {
  const load = useCallback(() => listTransfers({ direction, status: status === 'all' ? undefined : status }), [direction, status])
  const { result, setData } = useLoad(load)
  const [working, setWorking] = useState<number>()
  const [focusId, setFocusId] = useState<number>()
  const [error, setError] = useState<string>()
  const [announcement, setAnnouncement] = useState('')

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  /** Read the list again, so the transfers, their histories and their trips are all as the server now has them. */
  const reload = () =>
    load()
      .then((fresh) => setData(() => fresh))
      .catch(() => undefined)

  /** Run one save: busy while it runs, the failure in the alert, and a fresh list when the server says it moved on (409). */
  async function save(transferId: number, run: () => Promise<string>): Promise<boolean> {
    setError(undefined)
    setAnnouncement('')
    setWorking(transferId)
    try {
      setAnnouncement(await run())
      setFocusId(transferId)
      return true
    } catch (failure) {
      setError(transferFailure(failure))
      if (failure instanceof ApiError && failure.status === 409) await reload()
      return false
    } finally {
      setWorking(undefined)
    }
  }

  /** Make one move, then show the card as the server now has it and announce the new status (story #48). */
  async function act(transfer: Transfer, action: TransferAction, extra: { reason?: string } = {}) {
    await save(transfer.id, async () => {
      const updated = await postTransferAction(transfer.id, action, extra)
      setData((current) => current.map((t) => (t.id === updated.id ? updated : t)))
      return `Transfer #${updated.id} is now ${TRANSFER_STATUS_LABEL[updated.status].toLowerCase()}.`
    })
  }

  /** Send an ambulance for an approved transfer (story #51). The list is read again, so the trip shows on the card. */
  async function dispatch(transfer: Transfer, ambulanceId: number): Promise<boolean> {
    return save(transfer.id, async () => {
      const trip = await dispatchAmbulance(transfer.id, ambulanceId)
      await reload()
      return `Ambulance ${trip.ambulance.identifier} is on its way for transfer #${transfer.id}, about ${trip.etaMinutes} min.`
    })
  }

  /** One step of a trip (story #51). The transfer changes with departure, so the list is read again. */
  async function step(transfer: Transfer, trip: Trip, action: TripAction) {
    await save(transfer.id, async () => {
      const updated = await postTripAction(trip.id, action)
      await reload()
      return `Trip for transfer #${transfer.id} is now ${TRIP_STATUS_LABEL[updated.status].toLowerCase()}.`
    })
  }

  const transfers = result.data
  return (
    <>
      <FormAlert>{error}</FormAlert>
      <p role="status" className="visually-hidden">
        {announcement}
      </p>
      {transfers.length === 0 ? (
        <p>{status === 'all' ? 'No transfers yet.' : 'No transfers match. Choose another status.'}</p>
      ) : (
        <ul className={styles.cards}>
          {transfers.map((transfer) => (
            <li key={`${transfer.id}-${transfer.status}`}>
              <TransferCard
                transfer={transfer}
                direction={direction}
                busy={working !== undefined}
                onAction={act}
                onDispatch={dispatch}
                onTripStep={step}
                focus={focusId === transfer.id}
              />
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
