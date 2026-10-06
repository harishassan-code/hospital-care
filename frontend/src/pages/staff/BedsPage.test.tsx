import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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

const wardSection = (name: string) => screen.getByRole('region', { name: new RegExp(`^${name}`) })

async function startDischarge() {
  const [discharge] = await screen.findAllByRole('button', { name: /^Discharge / })
  const label = discharge.getAttribute('aria-label')!.replace('Discharge ', '')
  await userEvent.click(discharge)
  return { label, tile: screen.getByRole('listitem', { name: new RegExp(`^${label}`) }) }
}

describe('BedsPage', () => {
  it('shows every ward with its beds', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/beds')
    const icu = await screen.findByRole('region', { name: /^ICU/ })
    expect(within(icu).getAllByRole('listitem')).toHaveLength(10)
    for (const ward of ['HDU', 'Medical A', 'Surgical B', 'Paediatrics', 'Maternity', 'Isolation']) {
      expect(wardSection(ward)).toBeInTheDocument()
    }
  })

  it('discharges only after confirming, saves it, and shows the bed as the server saved it', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/beds')
    const { label, tile } = await startDischarge()
    expect(within(tile).getByText(/Discharge .+\?/)).toBeInTheDocument()
    await userEvent.click(within(tile).getByRole('button', { name: 'Confirm discharge' }))

    expect(await within(tile).findByText('Cleaning')).toBeInTheDocument()
    expect(within(tile).getByRole('button', { name: `Mark ready ${label}` })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(`${label} is now cleaning`)
    const post = fetchMock.mock.calls.find(([url, init]) => init?.method === 'POST' && String(url).includes('/actions/'))
    expect(String(post?.[0])).toContain(`/api/beds/${label}/actions/`)
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ action: 'discharge' })
  })

  it('cancelling the confirmation leaves the patient in the bed', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/beds')
    await startDischarge()
    await userEvent.click(screen.getByRole('button', { name: 'Keep patient' }))
    expect(screen.queryByRole('button', { name: 'Confirm discharge' })).toBeNull()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('explains a conflict and shows the latest state when someone else changed the bed first', async () => {
    const { board } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/beds')
    const { label, tile } = await startDischarge()
    const onServer = board.beds.find((b) => b.id === label)!
    Object.assign(onServer, { status: 'cleaning', patient: undefined, statusSince: new Date().toISOString() })

    await userEvent.click(within(tile).getByRole('button', { name: 'Confirm discharge' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Someone else changed this bed first')
    expect(within(screen.getByRole('listitem', { name: new RegExp(`^${label}`) })).getByText('Cleaning')).toBeInTheDocument()
  })

  it('filters by status', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/beds')
    await screen.findByRole('region', { name: /^ICU/ })
    await userEvent.click(screen.getByRole('button', { name: /^Free/ }))
    const tiles = within(screen.getByRole('main')).getAllByRole('listitem')
    expect(tiles.length).toBeGreaterThan(0)
    for (const tile of tiles) expect(within(tile).getByText('Free')).toBeInTheDocument()
  })

  it('is view-only for doctors', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/beds')
    await screen.findByRole('region', { name: /^ICU/ })
    expect(screen.queryAllByRole('button', { name: /^Discharge / })).toHaveLength(0)
    expect(screen.getByText(/View only/)).toBeInTheDocument()
  })
})
