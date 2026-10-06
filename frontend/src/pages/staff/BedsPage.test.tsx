import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { at } from '../../test/clock'
import { renderStaff } from '../../test/renderStaff'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(at('15:00'))
})
afterEach(() => vi.useRealTimers())

const wardSection = (name: string) => screen.getByRole('region', { name: new RegExp(`^${name}`) })

describe('BedsPage', () => {
  it('shows every ward with its beds', async () => {
    renderStaff('/staff/beds')
    const icu = await screen.findByRole('region', { name: /^ICU/ })
    expect(within(icu).getAllByRole('listitem')).toHaveLength(10)
    for (const ward of ['HDU', 'Medical A', 'Surgical B', 'Paediatrics', 'Maternity', 'Isolation']) {
      expect(wardSection(ward)).toBeInTheDocument()
    }
  })

  it('discharges a patient only after confirming, and the bed goes to cleaning', async () => {
    renderStaff('/staff/beds')
    const [discharge] = await screen.findAllByRole('button', { name: /^Discharge / })
    const label = discharge.getAttribute('aria-label')!.replace('Discharge ', '')
    await userEvent.click(discharge)
    const tile = screen.getByRole('listitem', { name: new RegExp(`^${label}`) })
    expect(within(tile).getByText(/Discharge .+\?/)).toBeInTheDocument()
    await userEvent.click(within(tile).getByRole('button', { name: 'Confirm discharge' }))
    expect(within(tile).getByText('Cleaning')).toBeInTheDocument()
    expect(within(tile).getByRole('button', { name: `Mark ready ${label}` })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(`${label} is now cleaning`)
  })

  it('cancelling the confirmation leaves the patient in the bed', async () => {
    renderStaff('/staff/beds')
    const [discharge] = await screen.findAllByRole('button', { name: /^Discharge / })
    await userEvent.click(discharge)
    await userEvent.click(screen.getByRole('button', { name: 'Keep patient' }))
    expect(screen.queryByRole('button', { name: 'Confirm discharge' })).toBeNull()
  })

  it('filters by status', async () => {
    renderStaff('/staff/beds')
    await screen.findByRole('region', { name: /^ICU/ })
    await userEvent.click(screen.getByRole('button', { name: /^Free/ }))
    const tiles = within(screen.getByRole('main')).getAllByRole('listitem')
    expect(tiles.length).toBeGreaterThan(0)
    for (const tile of tiles) expect(within(tile).getByText('Free')).toBeInTheDocument()
  })

  it('is view-only for doctors', async () => {
    renderStaff('/staff/beds')
    await screen.findByRole('region', { name: /^ICU/ })
    await userEvent.selectOptions(screen.getByLabelText('Viewing as'), 'Doctor')
    expect(screen.queryAllByRole('button', { name: /^Discharge / })).toHaveLength(0)
    expect(screen.getByText(/View only/)).toBeInTheDocument()
  })
})
