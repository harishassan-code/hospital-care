import { afterEach, describe, expect, it, vi } from 'vitest'
import { listNotifications, markNotificationRead, unreadCount } from './notifications'

const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => {
  vi.restoreAllMocks()
})

describe('listNotifications', () => {
  it('asks for all of them, or only the unread ones when told to', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, []))
    await listNotifications()
    await listNotifications({ unread: true })
    expect(String(fetchMock.mock.calls[0]![0])).toMatch(/\/notifications\/$/)
    expect(String(fetchMock.mock.calls[1]![0])).toMatch(/\/notifications\/\?unread=true$/)
  })

  it('returns the rows as the server sends them', async () => {
    const row = {
      id: 3,
      kind: 'transfer.requested',
      severity: 'critical',
      message: 'CityCare General asks for 2 of A+ red cells.',
      link: '/staff/transfers',
      createdAt: '2026-11-18T09:00:00Z',
      readAt: null,
    }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, [row]))
    expect(await listNotifications()).toEqual([row])
  })
})

describe('unreadCount', () => {
  it('reads the count from the unread-count endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, { count: 4 }))
    expect(await unreadCount()).toEqual({ count: 4 })
    expect(String(fetchMock.mock.calls[0]![0])).toMatch(/\/notifications\/unread-count\/$/)
  })
})

describe('markNotificationRead', () => {
  it('posts to the notification read endpoint and returns the row with its read time', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, { id: 7, readAt: '2026-11-18T09:05:00Z' }))
    expect(await markNotificationRead(7)).toEqual({ id: 7, readAt: '2026-11-18T09:05:00Z' })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toMatch(/\/notifications\/7\/read\/$/)
    expect(init?.method).toBe('POST')
  })

  it('rejects when the server says the notification is not the user\'s', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(404, { detail: 'Not found.' }))
    await expect(markNotificationRead(99)).rejects.toMatchObject({ status: 404 })
  })
})
