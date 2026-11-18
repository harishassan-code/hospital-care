import type { AvailableNeed, Need } from '../../api/emergencies'
import { ApiError, fieldErrors } from '../../api/client'
import { TRANSFER_STATUS_LABEL, type Transfer, type TransferHistoryEntry, type TransferResourceType, type TransferStatus } from '../../api/transfers'
import type { Tone } from '../../components/ui/StatusBadge'

/** The tone of each status badge. The words say the status; the tone only adds emphasis. */
export const TRANSFER_TONE: Record<TransferStatus, Tone> = {
  requested: 'neutral',
  approved: 'neutral',
  dispatched: 'neutral',
  inTransit: 'neutral',
  delivered: 'ok',
  rejected: 'warning',
  cancelled: 'neutral',
}

/** The transfer resource a need moves as. Beds and operating rooms don't move (patient transfer is a later bolt). */
export function transferTypeOf(need: Need): TransferResourceType | undefined {
  return need.type === 'blood' || need.type === 'equipment' ? need.type : undefined
}

/**
 * How many more of a need can be asked from other hospitals (story #47): what it still lacks, less the holds it has and
 * the requests still waiting for an answer. The server enforces the same limit.
 */
export function askableFor(need: AvailableNeed, transfers: Transfer[]): number {
  const waiting = transfers
    .filter((t) => t.itemId === need.itemId && t.status === 'requested')
    .reduce((sum, t) => sum + t.quantity, 0)
  return Math.max(0, need.remaining - need.reserved - waiting)
}

/** A status in words, whatever the server sent. */
export function statusWord(status: string): string {
  return Object.hasOwn(TRANSFER_STATUS_LABEL, status) ? TRANSFER_STATUS_LABEL[status as TransferStatus] : status
}

/** A history line: "Requested" for the request itself, then "Approved → Dispatched" for each later move. */
export function describeTransferMove(entry: TransferHistoryEntry): string {
  if (!entry.fromStatus) return 'Requested'
  return `${statusWord(entry.fromStatus)} → ${statusWord(entry.toStatus)}`
}

/**
 * Why a transfer move or request didn't happen: the server's words for a 4xx (its `detail`, or its field messages), and a
 * plain line for anything else, including a server that didn't answer.
 */
export function transferFailure(error: unknown): string {
  if (error instanceof ApiError && error.status !== 0 && error.status < 500) {
    const messages = Object.values(fieldErrors(error))
    return messages.length > 0 ? messages.join(' ') : 'Nothing changed. Check the details and try again.'
  }
  return 'The hospital’s system didn’t respond, so nothing changed. Try again.'
}
