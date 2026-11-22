import type { CaseStatus, EmergencyCase } from '../../api/emergencies'
import type { Transfer, TransferStatus } from '../../api/transfers'
import type { TransfersData } from '../staff/staffContext'

/** A case still needing stock: the same set the network feed lists (FEED_STATUSES in the emergencies views). */
const OPEN_CASE_STATUSES: readonly CaseStatus[] = ['open', 'matching', 'partiallyFulfilled', 'escalated']

/** A transfer still in progress. Delivered, rejected and cancelled transfers are finished. */
const PENDING_TRANSFER_STATUSES: readonly TransferStatus[] = ['requested', 'approved', 'dispatched', 'inTransit']

export interface RequestsSummary {
  /** null when the cases couldn't be loaded. */
  cases: { open: number; critical: number } | null
  /** null when the transfers couldn't be loaded. */
  transfers: { pending: number; toAnswer: number; outgoing: number } | null
}

const isPending = (t: Transfer) => PENDING_TRANSFER_STATUSES.includes(t.status)

function countCases(cases: EmergencyCase[]) {
  const open = cases.filter((c) => OPEN_CASE_STATUSES.includes(c.status))
  return { open: open.length, critical: open.filter((c) => c.severity === 'critical').length }
}

/**
 * Pending counts each transfer once: an admin's two lists are the same network-wide list, because the API ignores
 * `direction` when the user has no hospital.
 */
function countTransfers({ incoming, outgoing }: TransfersData) {
  const pendingOutgoing = outgoing.filter(isPending)
  return {
    pending: new Set([...incoming.filter(isPending), ...pendingOutgoing].map((t) => t.id)).size,
    toAnswer: incoming.filter((t) => t.status === 'requested').length,
    outgoing: pendingOutgoing.length,
  }
}

/** Every count the dashboard's request and transfer tiles show (B08). A null input gives null: that tile is unavailable. */
export function summarizeRequests(cases: EmergencyCase[] | null, transfers: TransfersData | null): RequestsSummary {
  return {
    cases: cases && countCases(cases),
    transfers: transfers && countTransfers(transfers),
  }
}
