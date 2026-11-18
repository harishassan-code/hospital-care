import { apiGet, apiPost } from './client'

/** Where a transfer stands (stories #47 to #49). The names match TRANSFER_LIFECYCLE in backend/apps/transfers/models.py. */
export type TransferStatus = 'requested' | 'approved' | 'dispatched' | 'inTransit' | 'delivered' | 'rejected' | 'cancelled'

/** A move along the transfer lifecycle. `startTransit` is "Mark in transit"; `deliver` is "Confirm receipt". */
export type TransferAction = 'approve' | 'reject' | 'dispatch' | 'startTransit' | 'deliver' | 'cancel'

export type TransferResourceType = 'blood' | 'equipment'

/** "incoming": asked of the user's hospital, which supplies. "outgoing": asked by it, to another hospital. */
export type TransferDirection = 'incoming' | 'outgoing'

/** One entry in a transfer's history, oldest first. The first is the request itself, with no `fromStatus`. */
export interface TransferHistoryEntry {
  fromStatus: string
  toStatus: string
  action: string
  note: string
  /** The user's name, or their email if they have no name. Null for a move the system made. */
  actor: string | null
  at: string
}

/**
 * A request for stock from one hospital to another, for one need of one case (story #47). Shape of `TransferSerializer`
 * in backend/apps/transfers/serializers.py.
 */
export interface Transfer {
  id: number
  case: { reference: string; severity: string }
  /** The need of the case this transfer is for. */
  itemId: number
  resourceType: TransferResourceType
  /** The need as staff name it: "O− red cells", "Ventilator". */
  need: string
  /** The hospital that supplies the stock. */
  supplier: { id: number; name: string }
  /** The hospital that asked: the case's own hospital. */
  receiver: { id: number; name: string }
  /** How many were asked for. */
  quantity: number
  /** How many the supplier has approved (set aside). Less than `quantity` after a partial approval. */
  approved: number
  /** The units set aside at the supplier for this transfer, as staff name them. */
  resources: string[]
  status: TransferStatus
  /** Why it was rejected or cancelled. Empty otherwise. */
  reason: string
  /** The person who asked, or their email if they have no name. */
  requestedBy: string
  createdAt: string
  history: TransferHistoryEntry[]
  /** The moves the signed-in user may make now. The page shows only these, as buttons. */
  actions: TransferAction[]
}

export const TRANSFER_STATUS_LABEL: Record<TransferStatus, string> = {
  requested: 'Requested',
  approved: 'Approved',
  dispatched: 'Dispatched',
  inTransit: 'In transit',
  delivered: 'Delivered',
  rejected: 'Rejected',
  cancelled: 'Cancelled',
}

export const TRANSFER_ACTION_LABEL: Record<TransferAction, string> = {
  approve: 'Approve',
  reject: 'Reject',
  dispatch: 'Mark dispatched',
  startTransit: 'Mark in transit',
  deliver: 'Confirm receipt',
  cancel: 'Cancel transfer',
}

/** Transfers the user's hospital is part of (admins: the whole network), newest first. GET /api/transfers/. */
export function listTransfers(filter: { direction?: TransferDirection; status?: TransferStatus } = {}): Promise<Transfer[]> {
  const query = new URLSearchParams()
  if (filter.direction) query.set('direction', filter.direction)
  if (filter.status) query.set('status', filter.status)
  const search = query.toString()
  return apiGet<Transfer[]>(`/transfers/${search ? `?${search}` : ''}`)
}

export interface TransferRequestInput {
  /** The case's need, an `itemId` of the case. */
  itemId: number
  supplierId: number
  quantity: number
  note?: string
}

/** Ask another hospital for stock for one need of a case. POST /api/transfers/ (transfers: edit). 400 when refused. */
export function requestTransfer(input: TransferRequestInput): Promise<Transfer> {
  return apiPost<Transfer>('/transfers/', input)
}

/** One transfer with its history and moves. GET /api/transfers/<id>/. 404 if neither hospital is the user's. */
export function getTransfer(id: number): Promise<Transfer> {
  return apiGet<Transfer>(`/transfers/${id}/`)
}

/**
 * Make one move on a transfer. POST /api/transfers/<id>/actions/. 400 with `reason` when a rejection has none, 403 when
 * the user's role can't make the move, 409 when the lifecycle doesn't allow it now (or no stock is free to approve).
 */
export function postTransferAction(
  id: number,
  action: TransferAction,
  extra: { reason?: string; note?: string } = {},
): Promise<Transfer> {
  return apiPost<Transfer>(`/transfers/${id}/actions/`, { action, ...extra })
}
