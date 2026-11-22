import { useCallback, useEffect, useState } from 'react'
import { acknowledge, getNotifications, getUnreadCount, type AppNotification } from '../../api/notifications'

export const POLL_MS = 30_000

/**
 * Server notifications for the bell and the critical banner (story #53). Polls every 30 s while the tab is
 * visible, and again when it comes back into view. A failed poll keeps the last known state.
 */
export function useNotifications() {
  const [unread, setUnread] = useState(0)
  const [critical, setCritical] = useState<AppNotification[]>([])

  const refresh = useCallback(async () => {
    const [count, banners] = await Promise.all([getUnreadCount(), getNotifications({ critical: true })]).catch(
      () => [null, null] as const,
    )
    if (count) setUnread(count.unread)
    if (banners) setCritical(banners)
  }, [])

  useEffect(() => {
    void refresh()
    const timer = setInterval(() => document.visibilityState !== 'hidden' && void refresh(), POLL_MS)
    const onVisible = () => document.visibilityState === 'visible' && void refresh()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [refresh])

  const ack = useCallback(
    async (id: number) => {
      setCritical((current) => current.filter((n) => n.id !== id))
      await acknowledge(id).catch(() => undefined)
      await refresh()
    },
    [refresh],
  )

  return { unread, critical, acknowledge: ack, refresh }
}
