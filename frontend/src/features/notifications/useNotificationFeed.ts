import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError } from '../../api/client'
import { listNotifications, markNotificationRead, unreadCount, type Notification } from '../../api/notifications'

/** How often the signed-in user's notifications are fetched again (B07, #53). */
export const NOTIFICATION_POLL_MS = 30_000

export interface NotificationFeed {
  /** The 50 newest notifications, read and unread. null until the first answer arrives. */
  all: Notification[] | null
  /** The unread ones, newest first, 50 at most: what the bell panel and the critical banners show. */
  unread: Notification[] | null
  /** How many are unread on the server (can be more than the 50 listed). */
  unreadCount: number
  /** True when the first fetch failed and nothing is on screen yet. */
  failed: boolean
  /** When the lists were last fetched successfully. null before that. */
  updatedAt: Date | null
  /** True when the last fetch failed: the lists are from `updatedAt`. */
  refreshFailed: boolean
  /** Marks one notification read on the server, then updates the lists and the count. Throws when the server refuses. */
  markRead: (id: number) => Promise<void>
}

type Lists = Pick<NotificationFeed, 'all' | 'unread' | 'unreadCount' | 'failed' | 'updatedAt' | 'refreshFailed'>

const EMPTY: Lists = { all: null, unread: null, unreadCount: 0, failed: false, updatedAt: null, refreshFailed: false }

/**
 * Fetches the signed-in user's notifications every 30 seconds, from mount until unmount (the staff session). While the tab
 * is hidden nothing is sent; when it is shown again one fetch runs at once and the timer restarts. A fetch that is still
 * running is never joined by another. A 401 or 403 stops polling. Any other failure keeps the last lists on screen.
 */
export function useNotificationFeed(): NotificationFeed {
  const [lists, setLists] = useState<Lists>(EMPTY)

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined
    let running = false
    let stopped = false

    const fetchAll = async () => {
      if (running || stopped) return
      running = true
      try {
        const [all, unread, { count }] = await Promise.all([listNotifications(), listNotifications({ unread: true }), unreadCount()])
        if (stopped) return
        setLists({ all, unread, unreadCount: count, failed: false, updatedAt: new Date(), refreshFailed: false })
      } catch (error) {
        if (stopped) return
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          stopped = true
          clearInterval(timer)
          return
        }
        setLists((current) => (current.all ? { ...current, refreshFailed: true } : { ...current, failed: true }))
      } finally {
        running = false
      }
    }

    const restart = () => {
      clearInterval(timer)
      timer = setInterval(() => {
        if (document.visibilityState !== 'hidden') void fetchAll()
      }, NOTIFICATION_POLL_MS)
    }
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible' && !stopped) {
        restart()
        void fetchAll()
      }
    }

    void fetchAll()
    restart()
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      stopped = true
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])

  const markRead = useCallback(async (id: number) => {
    const saved = await markNotificationRead(id)
    setLists((current) => ({
      ...current,
      all: current.all?.map((n) => (n.id === saved.id ? saved : n)) ?? null,
      unreadCount: current.unread?.some((n) => n.id === saved.id) ? Math.max(0, current.unreadCount - 1) : current.unreadCount,
      unread: current.unread?.filter((n) => n.id !== saved.id) ?? null,
    }))
  }, [])

  return useMemo(() => ({ ...lists, markRead }), [lists, markRead])
}
