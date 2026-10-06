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

const bodyRows = (table: HTMLElement) => within(table).getAllByRole('row').slice(1)

describe('BloodPage', () => {
  it('shows available stock for every component and group, flagging low groups', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/blood')
    const grid = await screen.findByRole('table', { name: /Available units by component and group/ })
    expect(bodyRows(grid)).toHaveLength(4)
    const redCells = within(grid).getByRole('row', { name: /^Red cells/ })
    expect(within(redCells).getAllByRole('cell')[0]).toHaveTextContent('3')
    expect(within(redCells).getAllByRole('cell')[0]).toHaveTextContent('Low')
  })

  it('finds compatible donor groups, reversing the rule for plasma', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/blood')
    const finder = await screen.findByRole('region', { name: 'Compatibility finder' })
    await userEvent.selectOptions(within(finder).getByLabelText('Patient’s blood group'), 'O−')
    const donors = () => within(within(finder).getByRole('list', { name: 'Compatible donor groups' })).getAllByRole('listitem')
    expect(donors().map((li) => li.querySelector('strong')?.textContent)).toEqual(['O−'])

    await userEvent.selectOptions(within(finder).getByLabelText('Patient’s blood group'), 'AB+')
    await userEvent.click(within(finder).getByRole('button', { name: 'Plasma' }))
    expect(donors().map((li) => li.querySelector('strong')?.textContent)).toEqual(['AB−', 'AB+'])
    expect(within(finder).getByText(/crossmatch/)).toBeInTheDocument()
  })

  it('lists units soonest-expiry first and filters by component', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/blood')
    const units = await screen.findByRole('region', { name: 'Units' })
    const table = within(units).getByRole('table')
    const expiries = bodyRows(table).map((row) => Number(row.getAttribute('data-expires')))
    expect(expiries).toEqual([...expiries].sort((a, b) => a - b))

    await userEvent.click(within(units).getByRole('button', { name: /^Platelets/ }))
    for (const row of bodyRows(table)) expect(row).toHaveTextContent('Platelets')
  })
})
