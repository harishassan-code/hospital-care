/**
 * QA test cases for the signed-in landing area, from the QA sheet (LAND-N*) by Muhammad Hassaan (PR #70).
 * In this project that area is the staff workspace at /staff. Each test name starts with its QA id;
 * LAND-N02 doesn't apply (one hospital per install) and is explained in the test report.
 */
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { BedBoard } from '../api/beds'
import { at } from '../test/clock'
import { sampleBedBoard } from '../test/fixtures/beds'
import { samplePublicStatus } from '../test/fixtures/publicStatus'
import { mockStaffApi } from '../test/mockApi'
import { renderStaff } from '../test/renderStaff'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(at('15:00'))
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const requested = (fetchMock: ReturnType<typeof mockStaffApi>['fetchMock']) =>
  fetchMock.mock.calls.map(([url, init]) => `${init?.method ?? 'GET'} ${new URL(String(url)).pathname}`)
const navLinks = () => within(screen.getByRole('navigation', { name: 'Staff' })).getAllByRole('link')
const tiles = () => screen.findByRole('list', { name: 'Status summary' })

describe('Staff workspace: negative cases (LAND-N)', () => {
  it('LAND-N01 signed-out visitors are sent to sign-in and never see the workspace', async () => {
    mockStaffApi({ role: null })
    renderStaff('/staff')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Staff' })).toBeNull()
  })

  it('LAND-N03 (ADAPTED) modules outside the role are hidden, never loaded, and blocked if opened directly', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff')
    await tiles()
    expect(navLinks().map((a) => a.textContent)).toEqual(['Overview', 'Beds', 'Pharmacy'])
    expect(requested(fetchMock)).not.toContain('GET /api/blood/units/')
    expect(screen.queryByText(/Blood bank/i, { selector: 'span' })).toBeNull()
  })

  it('LAND-N03 opening a blocked module by its address shows "no access"', async () => {
    mockStaffApi({ role: 'pharmacist' })
    renderStaff('/staff/beds')
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
  })

  it('LAND-N04 one failing source shows its own error while the rest keeps working', async () => {
    mockStaffApi({ role: 'admin', erDown: true })
    renderStaff('/staff')
    const summary = await tiles()
    expect(within(summary).getByText('Live status unavailable')).toBeInTheDocument()
    expect(within(summary).getByText(/of 106 beds/)).toBeInTheDocument()
  })

  it('LAND-N04 if the hospital system can’t be reached at all, the page says so plainly', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    renderStaff('/staff')
    expect(await screen.findByText(/hospital’s system didn’t respond/)).toBeInTheDocument()
  })

  it('LAND-N06 every navigation link goes to a real page', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    await tiles()
    expect(navLinks().map((a) => a.getAttribute('href'))).toEqual(['/staff', '/staff/beds', '/staff/blood', '/staff/pharmacy'])
    for (const [name, heading] of [
      ['Beds', 'Beds'],
      ['Blood bank', 'Blood bank'],
      ['Pharmacy', 'Pharmacy'],
      ['Overview', 'Overview'],
    ]) {
      await userEvent.click(screen.getByRole('link', { name }))
      expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
    }
  })

  it('LAND-N07 HTML in data from the server is shown as text, never run', async () => {
    const board: BedBoard = sampleBedBoard(new Date())
    const attack = '<img src=x onerror="window.__xss=1">'
    board.wards[0] = { ...board.wards[0], name: attack }
    mockStaffApi({ role: 'admin', board })
    renderStaff('/staff/beds')
    expect((await screen.findAllByText(attack, { exact: false })).length).toBeGreaterThan(0)
    expect(document.querySelectorAll('main img')).toHaveLength(0)
    expect((window as unknown as { __xss?: number }).__xss).toBeUndefined()
  })

  it('LAND-N08 signing out ends the session on the server; coming back asks for sign-in again', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    const { unmount } = renderStaff('/staff')
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(requested(fetchMock)).toContain('POST /api/auth/logout/')
    unmount()

    mockStaffApi({ role: null })
    renderStaff('/staff')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('LAND-N09 zero counts show as 0, never blank or NaN', async () => {
    const board = sampleBedBoard(new Date())
    board.beds = board.beds.map((b) => ({ ...b, status: 'occupied' as const }))
    const status = samplePublicStatus(new Date())
    mockStaffApi({ role: 'admin', board, publicStatus: { ...status, emergency: { ...status.emergency, waitingCount: 0, waitMinutes: 0 } } })
    renderStaff('/staff')
    const summary = await tiles()
    const [beds, er] = within(summary).getAllByRole('link')
    expect(beds).toHaveTextContent(/^Beds free\s*0 of 106 beds/)
    expect(er).toHaveTextContent(/^Emergency\s*0 waiting/)
    expect(summary.textContent).not.toMatch(/NaN|undefined/)
  })
})
