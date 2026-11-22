import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fail, mockApi, ok } from '../../test/mockApi'
import { sampleCommandCentre } from '../../test/fixtures/commandCentre'
import { REFRESH_MS } from './rules'
import { useCommandCentre } from './useCommandCentre'

const figures = sampleCommandCentre(new Date('2026-11-18T10:00:00Z'))

/** Switch the page between visible and hidden, as a browser does when the tab changes. */
function setVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
  document.dispatchEvent(new Event('visibilitychange'))
}

function commandCentreCalls(fetchMock: ReturnType<typeof mockApi>) {
  return fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/command-centre/')).length
}

/** The hook's own refresh timers: the ones made with the 60-second period. Other code (waitFor) makes timers too. */
function refreshTimers() {
  const calls = vi.mocked(setInterval).mock.calls
  const results = vi.mocked(setInterval).mock.results
  return calls.flatMap((call, i) => (call[1] === REFRESH_MS ? [{ tick: call[0] as () => void, id: results[i]!.value }] : []))
}

beforeEach(() => {
  vi.spyOn(globalThis, 'setInterval')
  vi.spyOn(globalThis, 'clearInterval')
})

afterEach(() => {
  setVisibility('visible')
  vi.restoreAllMocks()
  delete (document as { visibilityState?: unknown }).visibilityState
})

describe('useCommandCentre', () => {
  it('loads the figures when the page opens, then again every 60 seconds', async () => {
    const fetchMock = mockApi({ 'GET /command-centre/': ok(figures) })
    const { result } = renderHook(() => useCommandCentre())
    await waitFor(() => expect(result.current.state.kind).toBe('ready'))
    expect(refreshTimers()).toHaveLength(1)
    expect(REFRESH_MS).toBe(60_000)

    await act(async () => refreshTimers()[0]!.tick())
    await waitFor(() => expect(commandCentreCalls(fetchMock)).toBe(2))
  })

  it('stops reading while the tab is hidden, and reads at once when it is shown again', async () => {
    const fetchMock = mockApi({ 'GET /command-centre/': ok(figures) })
    const { result } = renderHook(() => useCommandCentre())
    await waitFor(() => expect(result.current.state.kind).toBe('ready'))
    const { id } = refreshTimers()[0]!

    setVisibility('hidden')
    expect(clearInterval).toHaveBeenCalledWith(id)

    setVisibility('visible')
    await waitFor(() => expect(commandCentreCalls(fetchMock)).toBe(2))
    expect(refreshTimers()).toHaveLength(2) // the first timer, then a new one when the tab came back
  })

  it('does not start a timer for a page that opens hidden, and starts one when it is shown', async () => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' })
    const fetchMock = mockApi({ 'GET /command-centre/': ok(figures) })
    const { result } = renderHook(() => useCommandCentre())
    await waitFor(() => expect(result.current.state.kind).toBe('ready'))
    expect(refreshTimers()).toHaveLength(0)

    setVisibility('visible')
    expect(refreshTimers()).toHaveLength(1)
    await waitFor(() => expect(commandCentreCalls(fetchMock)).toBe(2))
  })

  it('clears the timer and the listener on unmount', async () => {
    const fetchMock = mockApi({ 'GET /command-centre/': ok(figures) })
    const { result, unmount } = renderHook(() => useCommandCentre())
    await waitFor(() => expect(result.current.state.kind).toBe('ready'))
    const { id } = refreshTimers()[0]!

    unmount()
    expect(clearInterval).toHaveBeenCalledWith(id)
    const before = commandCentreCalls(fetchMock)
    setVisibility('visible')
    expect(commandCentreCalls(fetchMock)).toBe(before)
  })

  it('keeps the last figures and marks them stale when a refresh fails, then clears the mark', async () => {
    let down = false
    const fetchMock = mockApi({
      'GET /command-centre/': () => (down ? fail(503) : ok(figures)),
    })
    const { result } = renderHook(() => useCommandCentre())
    await waitFor(() => expect(result.current.state.kind).toBe('ready'))

    down = true
    setVisibility('hidden')
    setVisibility('visible')
    await waitFor(() => expect(result.current.state.kind === 'ready' && result.current.state.stale).toBe(true))
    expect(result.current.state.kind === 'ready' && result.current.state.figures).toEqual(figures)

    down = false
    setVisibility('hidden')
    setVisibility('visible')
    await waitFor(() => expect(result.current.state.kind === 'ready' && result.current.state.stale).toBe(false))
    expect(fetchMock).toHaveBeenCalled()
  })

  it('shows a failed state when the first load fails, and loads again on retry', async () => {
    let down = true
    mockApi({ 'GET /command-centre/': () => (down ? fail(503) : ok(figures)) })
    const { result } = renderHook(() => useCommandCentre())
    await waitFor(() => expect(result.current.state.kind).toBe('failed'))

    down = false
    act(() => result.current.retry())
    expect(result.current.state.kind).toBe('loading')
    await waitFor(() => expect(result.current.state.kind).toBe('ready'))
  })
})
