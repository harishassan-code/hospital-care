import { screen, waitFor, within } from '@testing-library/react'
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

  it('lets blood-bank staff register a new unit, which then shows up in the unit list', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/blood')
    await userEvent.click(await screen.findByRole('button', { name: 'Register a unit' }))
    const form = within(screen.getByRole('region', { name: 'Register a unit' }))
    await userEvent.type(form.getByLabelText('Unit ID'), 'G7731 26 999999')
    await userEvent.selectOptions(form.getByLabelText('Blood group'), 'AB−')
    await userEvent.selectOptions(form.getByLabelText('Component'), 'Platelets')
    await userEvent.click(form.getByRole('button', { name: 'Register unit' }))

    const units = await screen.findByRole('region', { name: 'Units' })
    await userEvent.click(within(units).getByRole('button', { name: 'Quarantined (testing)' }))
    expect(within(units).getByText('G7731 26 999999')).toBeInTheDocument()
    // The form collapses back to the toggle button after a successful save.
    expect(screen.getByRole('button', { name: 'Register a unit' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Register a unit' })).not.toBeInTheDocument()
  })

  it('rejects a duplicate unit ID without leaving the form', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/blood')
    await userEvent.click(await screen.findByRole('button', { name: 'Register a unit' }))
    const form = within(screen.getByRole('region', { name: 'Register a unit' }))
    await userEvent.type(form.getByLabelText('Unit ID'), 'G7731 26 100000')
    await userEvent.click(form.getByRole('button', { name: 'Register unit' }))
    expect(await screen.findByText('A unit with this ID already exists.')).toBeInTheDocument()
  })

  it('hides the register form and screening panel from roles that can only view the blood bank', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/blood')
    await screen.findByRole('region', { name: 'Units' })
    expect(screen.queryByRole('button', { name: 'Register a unit' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Screening' })).not.toBeInTheDocument()
  })

  async function registerUnit(id: string) {
    await userEvent.click(await screen.findByRole('button', { name: 'Register a unit' }))
    const form = within(screen.getByRole('region', { name: 'Register a unit' }))
    await userEvent.type(form.getByLabelText('Unit ID'), id)
    await userEvent.click(form.getByRole('button', { name: 'Register unit' }))
    await screen.findByRole('button', { name: 'Register a unit' }) // form collapsed back
  }

  it('releases a unit to available once every screening test passes', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/blood')
    await registerUnit('G7731 26 888001')

    const panel = within(await screen.findByRole('region', { name: 'Screening' }))
    await userEvent.selectOptions(panel.getByLabelText('Unit to screen'), 'G7731 26 888001')

    for (const label of ['HIV', 'Hepatitis B', 'Hepatitis C', 'Syphilis', 'Malaria']) {
      const row = within(screen.getByText(label).closest('li')!)
      await userEvent.click(row.getByRole('button', { name: 'Pass' }))
      if (label !== 'Malaria') await row.findByText('Passed')
    }

    // A released unit leaves the screening queue — it's no longer offered in the picker.
    await waitFor(() => expect(screen.queryByRole('option', { name: 'G7731 26 888001' })).not.toBeInTheDocument())
  })

  it('discards a unit immediately when a screening test fails, with a reason', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/blood')
    await registerUnit('G7731 26 888002')

    const panel = within(await screen.findByRole('region', { name: 'Screening' }))
    await userEvent.selectOptions(panel.getByLabelText('Unit to screen'), 'G7731 26 888002')
    const row = within(screen.getByText('HIV').closest('li')!)
    await userEvent.click(row.getByRole('button', { name: 'Fail' }))
    await userEvent.type(row.getByLabelText('Reason'), 'Reactive on initial screen')
    await userEvent.click(row.getByRole('button', { name: 'Confirm fail' }))

    const units = screen.getByRole('region', { name: 'Units' })
    await userEvent.click(within(units).getByRole('button', { name: 'Discarded' }))
    expect(within(units).getByText('G7731 26 888002')).toBeInTheDocument()
  })

  it('requires a reason before confirming a failed test', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/blood')
    await registerUnit('G7731 26 888003')

    const panel = within(await screen.findByRole('region', { name: 'Screening' }))
    await userEvent.selectOptions(panel.getByLabelText('Unit to screen'), 'G7731 26 888003')
    const row = within(screen.getByText('HIV').closest('li')!)
    await userEvent.click(row.getByRole('button', { name: 'Fail' }))
    await userEvent.click(row.getByRole('button', { name: 'Confirm fail' }))
    expect(await screen.findByText('Say why the test failed.')).toBeInTheDocument()
  })
})
