import type { Notification } from '../../api/notifications'
import { minutesFrom } from '../clock'

/** A few notifications for the signed-in user, as B06's API returns them: newest first, the critical one unread. */
export function sampleNotifications(now: Date): Notification[] {
  return [
    {
      id: 3,
      kind: 'case.escalated',
      severity: 'critical',
      message: 'Case EC-2026-0007 escalated: no blood match yet.',
      link: '/staff/emergencies/EC-2026-0007',
      createdAt: minutesFrom(now, -2),
      readAt: null,
    },
    {
      id: 2,
      kind: 'reservation.made',
      severity: 'info',
      message: 'Two units of O+ red cells held for case EC-2026-0006.',
      link: '/staff/emergencies/EC-2026-0006',
      createdAt: minutesFrom(now, -20),
      readAt: minutesFrom(now, -15),
    },
    {
      id: 1,
      kind: 'transfer.requested',
      severity: 'critical',
      message: 'CityCare East asks for 2 of A+ red cells.',
      link: '/staff/transfers',
      createdAt: minutesFrom(now, -45),
      readAt: null,
    },
  ]
}
