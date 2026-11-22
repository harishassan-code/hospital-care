import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Notification } from '../../api/notifications'
import { at, minutesFrom } from '../../test/clock'
import { mockStaffApi } from '../../test/mockApi'
import { sampleNotifications } from '../../test/fixtures/notifications'
import { renderStaff } from '../../test/renderStaff'
import { NOTIFICATION_POLL_MS } from './useNotificationFeed'

type FetchMock = ReturnType<typeof mockStaffApi>['fetchMock']

let visibility: DocumentVisibilityState = 'visible'

beforeEach(() => {
  // Faked: the clock and the 30-second interval. setTimeout stays real, so findBy… still works.
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
  vi.setSystemTime(at('15:00'))
  visibility = 'visible'
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility })
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  delete (document as { visibilityState?: unknown }).visibilityState
})

const now = () => at('15:00')

/** Advance the fake clock and let React and the mocked responses settle. */
const advance = (ms: number) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })

/** How many times the list (all rows, not `?unread=true`) has been fetched. */
function listCalls(fetchMock: FetchMock): number {
  return fetchMock.mock.calls.filter(([url]) => {
    const u = new URL(String(url))
    return u.pathname === '/api/notifications/' && u.searchParams.get('unread') === null
  }).length
}

/** Make calls to one path answer with `status` while `failing()` is true; every other call is answered as usual. */
function failWhile(fetchMock: FetchMock, path: string, failing: () => boolean, status = 500) {
  const answer = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((input, init) =>
    new URL(String(input)).pathname === path && failing() ? Promise.resolve(new Response('{}', { status })) : answer(input, init),
  )
}

/** A notification for a long list: unread, routine, so only the count matters. */
const routine = (i: number): Notification => ({
  id: 1000 + i,
  kind: 'reservation.made',
  severity: 'info',
  message: `Routine event ${i}`,
  link: '',
  createdAt: minutesFrom(now(), -i),
  readAt: null,
})

const bellName = (unread: number) => new RegExp(`^${unread} unread notifications? and \\d+ items? need attention$`)

/** The unread count and the attention count the bell's name gives. */
function bellCounts(bell: HTMLElement) {
  const [, unread, items] = /^(\d+) unread notifications? and (\d+) items? need/.exec(bell.getAttribute('aria-label') ?? '') ?? []
  return { unread: Number(unread), items: Number(items) }
}

describe('polling', () => {
  it('fetches the alerts every 30 seconds, and not before', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    renderStaff('/staff')
    await screen.findByRole('button', { name: bellName(2) })
    expect(listCalls(fetchMock)).toBe(1)

    await advance(NOTIFICATION_POLL_MS - 1)
    expect(listCalls(fetchMock)).toBe(1)

    await advance(1)
    expect(listCalls(fetchMock)).toBe(2)
  })

  it('sends nothing while the tab is hidden, and refreshes once at once when it is shown again', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    renderStaff('/staff')
    await screen.findByRole('button', { name: bellName(2) })

    visibility = 'hidden'
    await advance(3 * NOTIFICATION_POLL_MS)
    expect(listCalls(fetchMock)).toBe(1)

    visibility = 'visible'
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    expect(listCalls(fetchMock)).toBe(2)

    // The timer restarted when the tab came back, so the next refresh is one full interval later.
    await advance(NOTIFICATION_POLL_MS - 1)
    expect(listCalls(fetchMock)).toBe(2)
    await advance(1)
    expect(listCalls(fetchMock)).toBe(3)
  })

  it('never starts a fetch while the previous one is still running', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    const answer = fetchMock.getMockImplementation()!
    let release!: () => void
    const held = new Promise<void>((resolve) => (release = resolve))
    let held1 = true
    fetchMock.mockImplementation(async (input, init) => {
      const u = new URL(String(input))
      if (u.pathname === '/api/notifications/' && u.searchParams.get('unread') === null && held1) {
        held1 = false
        await held
      }
      return answer(input, init)
    })

    renderStaff('/staff')
    await advance(3 * NOTIFICATION_POLL_MS)
    expect(listCalls(fetchMock)).toBe(1)

    await act(async () => release())
    await advance(NOTIFICATION_POLL_MS)
    expect(listCalls(fetchMock)).toBe(2)
  })

  it('stops asking after a 403 and keeps no alerts on screen for a patient or a signed-out user', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    failWhile(fetchMock, '/api/notifications/', () => true, 403)
    renderStaff('/staff')
    await screen.findByRole('button', { name: bellName(0) })
    expect(listCalls(fetchMock)).toBe(1)

    await advance(5 * NOTIFICATION_POLL_MS)
    expect(listCalls(fetchMock)).toBe(1)
  })

  it('keeps the last alerts on screen when a refresh fails, says when they were last updated, and recovers', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    let down = false
    failWhile(fetchMock, '/api/notifications/', () => down)
    renderStaff('/staff')
    await screen.findByRole('button', { name: bellName(2) })

    down = true
    await advance(NOTIFICATION_POLL_MS)
    expect(await screen.findByText('Couldn’t update alerts. Showing alerts from 15:00.')).toBeInTheDocument()
    // The critical banner still shows the alert it showed before the failed refresh.
    expect(within(screen.getByRole('region', { name: 'Critical alerts' })).getAllByRole('alert')).toHaveLength(2)

    down = false
    await advance(NOTIFICATION_POLL_MS)
    await waitFor(() => expect(screen.queryByText(/Couldn’t update alerts/)).toBeNull())
  })
})

describe('bell', () => {
  it('shows the unread count and the attention count in the badge, and says both in its name', async () => {
    mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    renderStaff('/staff')
    const bell = await screen.findByRole('button', { name: bellName(2) })
    const { items } = bellCounts(bell)
    expect(bell).toHaveAttribute('aria-label', expect.stringMatching(/^2 unread notifications and \d+ items? need attention$/))
    expect(within(bell).getByText(String(2 + items))).toBeInTheDocument()
  })

  it('reads 1 notification in the singular', async () => {
    mockStaffApi({ role: 'nurse', notifications: [sampleNotifications(now())[0]] })
    renderStaff('/staff')
    expect(await screen.findByRole('button', { name: /^1 unread notification and \d+ items? need attention$/ })).toBeInTheDocument()
  })

  it('shows 99+ above 99', async () => {
    mockStaffApi({ role: 'nurse', notifications: Array.from({ length: 120 }, (_, i) => routine(i)) })
    renderStaff('/staff')
    const bell = await screen.findByRole('button', { name: bellName(120) })
    expect(within(bell).getByText('99+')).toBeInTheDocument()
  })

  it('opens a panel of unread alerts, newest first; Escape closes it and returns focus to the bell', async () => {
    mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    renderStaff('/staff')
    const bell = await screen.findByRole('button', { name: bellName(2) })
    expect(screen.queryByRole('region', { name: 'Unread alerts' })).toBeNull()

    await userEvent.click(bell)
    expect(bell).toHaveAttribute('aria-expanded', 'true')
    const panel = screen.getByRole('region', { name: 'Unread alerts' })
    const messages = within(panel).getAllByRole('listitem').map((li) => li.textContent)
    expect(messages).toHaveLength(2)
    expect(messages[0]).toContain('Case EC-2026-0007 escalated')
    expect(messages[1]).toContain('CityCare East asks for 2 of A+ red cells.')
    expect(within(panel).getByRole('link', { name: 'All alerts' })).toHaveAttribute('href', '/staff/alerts')

    await userEvent.keyboard('{Escape}')
    expect(bell).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('region', { name: 'Unread alerts' })).toBeNull()
    expect(bell).toHaveFocus()
  })

  it('closes when the bell is pressed again', async () => {
    mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    renderStaff('/staff')
    const bell = await screen.findByRole('button', { name: bellName(2) })
    await userEvent.click(bell)
    await userEvent.click(bell)
    expect(bell).toHaveAttribute('aria-expanded', 'false')
  })

  it('says there are no unread alerts when there are none', async () => {
    mockStaffApi({ role: 'nurse', notifications: [] })
    renderStaff('/staff')
    const bell = await screen.findByRole('button', { name: bellName(0) })
    await userEvent.click(bell)
    expect(screen.getByText('No unread notifications.')).toBeInTheDocument()
  })

  it('reports a failed first load in the panel, with the hospital phone number', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    failWhile(fetchMock, '/api/notifications/', () => true)
    renderStaff('/staff')
    const bell = await screen.findByRole('button', { name: bellName(0) })
    await userEvent.click(bell)
    expect(await screen.findByText(/didn’t respond/)).toBeInTheDocument()
  })

  it('marks an alert read from the panel, and the badge and the banner update at once', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    renderStaff('/staff')
    const bell = await screen.findByRole('button', { name: bellName(2) })
    await userEvent.click(bell)
    await userEvent.click(screen.getByRole('button', { name: 'Mark read: CityCare East asks for 2 of A+ red cells.' }))

    await waitFor(() => expect(bell).toHaveAccessibleName(bellName(1)))
    expect(within(screen.getByRole('region', { name: 'Unread alerts' })).queryByText(/CityCare East/)).toBeNull()
    expect(within(screen.getByRole('region', { name: 'Critical alerts' })).queryByText(/CityCare East/)).toBeNull()
    expect(requestedPaths(fetchMock)).toContain('/api/notifications/1/read/')
  })

  it('says so beside the row when Mark read fails, and keeps the row unread', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    failWhile(fetchMock, '/api/notifications/1/read/', () => true)
    renderStaff('/staff')
    const bell = await screen.findByRole('button', { name: bellName(2) })
    await userEvent.click(bell)
    await userEvent.click(screen.getByRole('button', { name: 'Mark read: CityCare East asks for 2 of A+ red cells.' }))

    expect(await screen.findByText('This alert couldn’t be marked as read. Try again.')).toBeInTheDocument()
    expect(bell).toHaveAccessibleName(bellName(2))
    expect(screen.getByRole('button', { name: 'Mark read: CityCare East asks for 2 of A+ red cells.' })).toBeInTheDocument()
  })
})

describe('critical banner', () => {
  it('shows each unread critical alert, and acknowledging one removes it everywhere', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    renderStaff('/staff')
    const banners = await screen.findByRole('region', { name: 'Critical alerts' })
    expect(within(banners).getAllByRole('alert')).toHaveLength(2)

    await userEvent.click(within(banners).getByRole('button', { name: 'Acknowledge: Case EC-2026-0007 escalated: no blood match yet.' }))
    await waitFor(() => expect(within(banners).getAllByRole('alert')).toHaveLength(1))
    expect(requestedPaths(fetchMock)).toContain('/api/notifications/3/read/')
    expect(await screen.findByRole('button', { name: bellName(1) })).toBeInTheDocument()
  })

  it('is not drawn when no critical alert is unread', async () => {
    mockStaffApi({ role: 'nurse', notifications: [{ ...sampleNotifications(now())[1], readAt: null }] })
    renderStaff('/staff')
    await screen.findByRole('button', { name: bellName(1) })
    expect(screen.queryByRole('region', { name: 'Critical alerts' })).toBeNull()
  })

  it('shows three at most, and a line with a link for the rest', async () => {
    const critical = Array.from({ length: 5 }, (_, i) => ({ ...routine(i), id: 2000 + i, severity: 'critical' as const, message: `Critical event ${i}` }))
    mockStaffApi({ role: 'nurse', notifications: critical })
    renderStaff('/staff')
    const banners = await screen.findByRole('region', { name: 'Critical alerts' })
    expect(within(banners).getAllByRole('alert')).toHaveLength(3)
    expect(within(banners).getByText('2 more critical alerts.')).toBeInTheDocument()
    expect(within(banners).getByRole('link', { name: 'See all alerts' })).toHaveAttribute('href', '/staff/alerts')
  })

  it('shows on every staff page, the Overview included, and stays after a page change', async () => {
    mockStaffApi({ role: 'nurse', notifications: sampleNotifications(now()) })
    renderStaff('/staff')
    await screen.findByRole('region', { name: 'Critical alerts' })
    await userEvent.click(screen.getByRole('link', { name: 'Beds' }))
    expect(await screen.findByRole('region', { name: 'Critical alerts' })).toBeInTheDocument()
  })
})

function requestedPaths(fetchMock: FetchMock): string[] {
  return fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname)
}
