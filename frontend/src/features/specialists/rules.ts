import type { OnCallWindow } from '../../api/specialists'
import { karachiClock, karachiDate } from './schedule'

/*
 * The on-call rules the browser needs: what the server decides, mirrored for the fake server in tests and for the
 * detail page's "remove" button. The server is the authority; these only decide what to show.
 */

const ms = (iso: string) => Date.parse(iso)

/** Whether a window covers `now`. Start is inclusive and end exclusive, as on the server. */
export function coversNow(window: Pick<OnCallWindow, 'startsAt' | 'endsAt'>, now: Date): boolean {
  return ms(window.startsAt) <= now.getTime() && now.getTime() < ms(window.endsAt)
}

/** Whether a window has started by `now`. A started window stays as history and can't be removed. */
export function hasStarted(window: Pick<OnCallWindow, 'startsAt'>, now: Date): boolean {
  return ms(window.startsAt) <= now.getTime()
}

/**
 * The first window that shares any time with [startsAt, endsAt), or undefined. Windows that only touch don't clash.
 * `windows` must be in start order, so the same window is named as the server names it.
 */
export function clashing(windows: readonly OnCallWindow[], startsAt: string, endsAt: string): OnCallWindow | undefined {
  return windows.find((w) => ms(w.startsAt) < ms(endsAt) && ms(startsAt) < ms(w.endsAt))
}

/** The server's words for an overlap, e.g. "Overlaps an on-call window from 18 Nov 08:00 to 18 Nov 20:00." */
export function clashMessage(window: OnCallWindow): string {
  const from = `${karachiDate(window.startsAt)} ${karachiClock(window.startsAt)}`
  const to = `${karachiDate(window.endsAt)} ${karachiClock(window.endsAt)}`
  return `Overlaps an on-call window from ${from} to ${to}.`
}
