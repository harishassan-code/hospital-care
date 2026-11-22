import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { sampleNotifications } from '../../test/fixtures/notifications'
import { at } from '../../test/clock'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(at('15:00'))
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

/** The alerts page's panel, once the route has rendered. */
const pageRegion = () => screen.findByRole('region', { name: 'Your alerts' })
/** The page's rows, once the first answer has arrived. */
const loadedRows = async () => within(await pageRegion()).findAllByRole('listitem')
const rowsIn = (region: HTMLElement) => within(region).getAllByRole('listitem')

describe('Alerts page', () => {
  it('lists every alert newest first, and marks the unread ones in words', async () => {
    mockStaffApi({ role: 'nurse', notifications: sampleNotifications(at('15:00')) })
    renderStaff('/staff/alerts')
    await loadedRows()
    const rows = rowsIn(await pageRegion())
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent('Case EC-2026-0007 escalated')
    expect(rows[1]).toHaveTextContent('Two units of O+ red cells held')
    expect(rows[2]).toHaveTextContent('CityCare East asks for 2 of A+ red cells.')

    expect(within(rows[0]).getByText('Critical')).toBeInTheDocument()
    expect(within(rows[0]).getByText('Unread')).toBeInTheDocument()
    expect(within(rows[1]).queryByText('Unread')).toBeNull()
    expect(within(rows[1]).queryByRole('button', { name: /Mark read/ })).toBeNull()
    expect(within(rows[0]).getByRole('link', { name: /Open: Case EC-2026-0007/ })).toHaveAttribute('href', '/staff/emergencies/EC-2026-0007')
  })

  it('filters to unread alerts, and marks the active filter with aria-pressed', async () => {
    mockStaffApi({ role: 'nurse', notifications: sampleNotifications(at('15:00')) })
    renderStaff('/staff/alerts')
    await loadedRows()
    const all = screen.getByRole('button', { name: 'All' })
    const unread = screen.getByRole('button', { name: 'Unread' })
    expect(all).toHaveAttribute('aria-pressed', 'true')
    expect(unread).toHaveAttribute('aria-pressed', 'false')

    await userEvent.click(unread)
    expect(unread).toHaveAttribute('aria-pressed', 'true')
    expect(all).toHaveAttribute('aria-pressed', 'false')
    expect(rowsIn(await pageRegion())).toHaveLength(2)
    expect(within(await pageRegion()).queryByText(/Two units of O\+/)).toBeNull()
  })

  it('says there are no alerts yet, or no unread ones, when the list is empty', async () => {
    mockStaffApi({ role: 'nurse', notifications: [] })
    renderStaff('/staff/alerts')
    const region = await pageRegion()
    expect(await within(region).findByText('No notifications yet.')).toBeInTheDocument()
    await userEvent.click(within(region).getByRole('button', { name: 'Unread' }))
    expect(within(region).getByText('No unread notifications.')).toBeInTheDocument()
  })

  it('marking an alert read here updates the page, the bell and the banner at once', async () => {
    mockStaffApi({ role: 'nurse', notifications: sampleNotifications(at('15:00')) })
    renderStaff('/staff/alerts')
    await loadedRows()
    await userEvent.click(screen.getByRole('button', { name: 'Mark read: CityCare East asks for 2 of A+ red cells.' }))

    const region = await pageRegion()
    const rows = rowsIn(region)
    await waitFor(() => expect(within(rows[2]).queryByText('Unread')).toBeNull())
    expect(screen.getByRole('button', { name: /^1 unread notification and/ })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Critical alerts' })).queryByText(/CityCare East/)).toBeNull()
  })

  it('shows the loading text until the first answer arrives, and the failed text when it never does', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    const answer = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input, init) =>
      new URL(String(input)).pathname === '/api/notifications/' ? Promise.resolve(new Response('{}', { status: 500 })) : answer(input, init),
    )
    renderStaff('/staff/alerts')
    expect(await within(await pageRegion()).findByText(/didn’t respond/)).toHaveAttribute('role', 'status')
  })

  it('shows Loading… while the first answer is on its way', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse', notifications: sampleNotifications(at('15:00')) })
    const answer = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input, init) =>
      new URL(String(input)).pathname === '/api/notifications/' ? new Promise(() => undefined) : answer(input, init),
    )
    renderStaff('/staff/alerts')
    expect(await within(await pageRegion()).findByText('Loading…')).toHaveAttribute('role', 'status')
  })
})
