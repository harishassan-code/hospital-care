import { apiGet, apiPost } from './client'

/** `critical` needs an answer soon (the banner in B07). `info` shows in the list only. */
export type NotificationSeverity = 'critical' | 'info'

/**
 * One notification for the signed-in user (story #52). Shape of `NotificationSerializer` in
 * backend/apps/notifications/serializers.py. A user sees only their own.
 */
export interface Notification {
  id: number
  /** The event, e.g. "transfer.requested" or "case.escalated". */
  kind: string
  severity: NotificationSeverity
  message: string
  /** A staff page to open the event, e.g. "/staff/transfers". Empty when there is no page. */
  link: string
  createdAt: string
  /** When the person marked it read. Null until then. */
  readAt: string | null
}

/** The signed-in user's notifications, newest first, 50 at most. `unread: true` keeps only the unread ones. GET /api/notifications/. */
export function listNotifications(filter: { unread?: boolean } = {}): Promise<Notification[]> {
  return apiGet<Notification[]>(`/notifications/${filter.unread ? '?unread=true' : ''}`)
}

/** How many of the signed-in user's notifications are unread. GET /api/notifications/unread-count/. */
export function unreadCount(): Promise<{ count: number }> {
  return apiGet<{ count: number }>('/notifications/unread-count/')
}

/**
 * Mark one of the user's notifications read. POST /api/notifications/<id>/read/. Marking it again returns it as it is,
 * with the first time. 404 for another person's notification.
 */
export function markNotificationRead(id: number): Promise<Notification> {
  return apiPost<Notification>(`/notifications/${id}/read/`, undefined)
}
