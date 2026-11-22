import { apiGet, apiPost } from './client'

export type NotificationSeverity = 'info' | 'warning' | 'critical'

/** One server notification (story #52). Shape of NotificationSerializer in backend/apps/notifications/views.py. */
export interface AppNotification {
  id: number
  kind: string
  severity: NotificationSeverity
  title: string
  body: string
  link: string
  createdAt: string
  read: boolean
  acknowledged: boolean
}

export interface UnreadCount {
  unread: number
  critical: number
}

export function getNotifications(filter: { unread?: boolean; critical?: boolean } = {}): Promise<AppNotification[]> {
  const query = new URLSearchParams()
  if (filter.unread) query.set('unread', '1')
  if (filter.critical) query.set('critical', '1')
  const q = query.toString()
  return apiGet<AppNotification[]>(`/notifications/${q ? `?${q}` : ''}`)
}

export function getUnreadCount(): Promise<UnreadCount> {
  return apiGet<UnreadCount>('/notifications/unread-count/')
}

export function markRead(id: number): Promise<void> {
  return apiPost<void>(`/notifications/${id}/read/`, {})
}

export function markAllRead(): Promise<{ marked: number }> {
  return apiPost<{ marked: number }>('/notifications/read-all/', {})
}

export function acknowledge(id: number): Promise<void> {
  return apiPost<void>(`/notifications/${id}/acknowledge/`, {})
}
