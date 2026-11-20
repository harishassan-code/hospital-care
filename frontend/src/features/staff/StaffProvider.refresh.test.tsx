import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { useState } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { at } from '../../test/clock'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'
import StaffLayout from './StaffLayout'

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

const RELOAD_MS = 30_000

/** Advance the fake clock and let React and the mocked responses settle. */
const advance = (ms: number) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })

/** How many times each API path has been called (sign-in is left out: it happens once, not on each reload). */
function callCounts(fetchMock: FetchMock): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const [url] of fetchMock.mock.calls) {
    const path = new URL(String(url)).pathname
    if (path.startsWith('/api/auth/')) continue
    counts[path] = (counts[path] ?? 0) + 1
  }
  return counts
}

/** Make calls to one path fail with a 500 while `failing()` is true; every other call is answered as usual. */
function failWhile(fetchMock: FetchMock, path: string, failing: () => boolean) {
  const answer = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((input, init) =>
    new URL(String(input)).pathname === path && failing()
      ? Promise.resolve(new Response('{}', { status: 500 }))
      : answer(input, init),
  )
}

const tiles = () => screen.getByRole('list', { name: 'Status summary' })

describe('live refresh of the staff workspace', () => {
  it('reloads the data after 30 seconds, and not before', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    await screen.findByRole('list', { name: 'Status summary' })
    expect(callCounts(fetchMock)['/api/beds/']).toBe(1)

    await advance(RELOAD_MS - 1)
    expect(callCounts(fetchMock)['/api/beds/']).toBe(1)

    await advance(1)
    expect(callCounts(fetchMock)['/api/beds/']).toBe(2)
    expect(callCounts(fetchMock)['/api/emergencies/']).toBe(2)
  })

  it('makes the same calls on each reload as on the first load, for the role', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    renderStaff('/staff')
    await screen.findByRole('list', { name: 'Status summary' })
    const firstLoad = callCounts(fetchMock)
    expect(firstLoad['/api/transfers/']).toBe(2)

    await advance(RELOAD_MS)
    const reload = callCounts(fetchMock)
    expect(reload).toEqual(Object.fromEntries(Object.entries(firstLoad).map(([path, n]) => [path, n * 2])))
  })

  it('does not ask for modules the role cannot see on a reload', async () => {
    const { fetchMock } = mockStaffApi({ role: 'pharmacist' })
    renderStaff('/staff')
    await screen.findByRole('list', { name: 'Status summary' })
    await advance(RELOAD_MS)
    const counts = callCounts(fetchMock)
    expect(counts['/api/pharmacy/stock/']).toBe(2)
    expect(counts['/api/emergencies/']).toBe(2)
    expect(counts['/api/beds/']).toBeUndefined()
    expect(counts['/api/blood/units/']).toBeUndefined()
    expect(counts['/api/transfers/']).toBeUndefined()
  })

  it('does not reload while the tab is hidden, and reloads once when it is shown again', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    await screen.findByRole('list', { name: 'Status summary' })

    visibility = 'hidden'
    await advance(3 * RELOAD_MS)
    expect(callCounts(fetchMock)['/api/beds/']).toBe(1)

    visibility = 'visible'
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    expect(callCounts(fetchMock)['/api/beds/']).toBe(2)

    await advance(RELOAD_MS)
    expect(callCounts(fetchMock)['/api/beds/']).toBe(3)
  })

  it('never starts a reload while the previous one is still running', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    const answer = fetchMock.getMockImplementation()!
    let bedRequests = 0
    let finish!: () => void
    const slow = new Promise<void>((resolve) => (finish = resolve))
    fetchMock.mockImplementation(async (input, init) => {
      if (new URL(String(input)).pathname === '/api/beds/' && ++bedRequests === 2) await slow
      return answer(input, init)
    })

    renderStaff('/staff')
    await screen.findByRole('list', { name: 'Status summary' })

    await advance(RELOAD_MS) // starts the second reload, which is held up
    expect(bedRequests).toBe(2)
    await advance(2 * RELOAD_MS) // both ticks land while it runs and are skipped
    expect(bedRequests).toBe(2)

    await act(async () => finish())
    await advance(RELOAD_MS)
    expect(bedRequests).toBe(3)
  })

  it('keeps the data on screen when a reload fails, says so with the last good time, and recovers on a later tick', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    let casesDown = false
    failWhile(fetchMock, '/api/emergencies/', () => casesDown)
    renderStaff('/staff')
    expect(await screen.findByText('Updated 15:00')).toBeInTheDocument()
    expect(within(tiles()).getByText(/of 106 beds/)).toBeInTheDocument()

    casesDown = true
    await advance(RELOAD_MS)
    expect(await screen.findByText("Couldn’t update. Showing data from 15:00.")).toBeInTheDocument()
    expect(within(tiles()).getByText(/of 106 beds/)).toBeInTheDocument()
    expect(within(tiles()).getByRole('link', { name: /Open requests/ })).toHaveTextContent('2 open cases')

    await advance(RELOAD_MS)
    expect(callCounts(fetchMock)['/api/emergencies/']).toBe(3)

    casesDown = false
    await advance(RELOAD_MS)
    expect(await screen.findByText('Updated 15:01')).toBeInTheDocument()
  })

  it('shows the first-load message, and keeps trying, when the first load fails', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    let bedsDown = true
    failWhile(fetchMock, '/api/beds/', () => bedsDown)
    renderStaff('/staff')
    expect(await screen.findByText(/didn’t respond/)).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Status summary' })).toBeNull()

    bedsDown = false
    await advance(RELOAD_MS)
    expect(await screen.findByRole('list', { name: 'Status summary' })).toBeInTheDocument()
    expect(screen.getByText('Updated 15:00')).toBeInTheDocument()
  })

  it('reloads without showing "Loading…" again, and keeps what a child has typed', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    function Note() {
      const [text, setText] = useState('')
      return (
        <label>
          Note
          <input value={text} onChange={(e) => setText(e.target.value)} />
        </label>
      )
    }
    render(
      <MemoryRouter initialEntries={['/staff']}>
        <Routes>
          <Route path="/staff" element={<StaffLayout />}>
            <Route index element={<Note />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )
    fireEvent.change(await screen.findByLabelText('Note'), { target: { value: 'draft handover' } })

    await advance(RELOAD_MS)
    expect(callCounts(fetchMock)['/api/beds/']).toBe(2)
    expect(screen.getByLabelText('Note')).toHaveValue('draft handover')
    expect(screen.queryByText('Loading…')).toBeNull()
  })
})
