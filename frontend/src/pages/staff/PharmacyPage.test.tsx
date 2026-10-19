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

const medicineRows = async () => {
  const table = await screen.findByRole('table', { name: /Medicine stock/ })
  return within(table)
    .getAllByRole('row')
    .filter((row) => row.dataset.medicine)
}

describe('PharmacyPage', () => {
  it('lists the formulary with high-alert and controlled-drug flags', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/pharmacy')
    expect(await medicineRows()).toHaveLength(23)
    const morphine = screen.getByRole('row', { name: /^Morphine/ })
    expect(within(morphine).getByText('High-alert')).toBeInTheDocument()
    expect(within(morphine).getByText('CD')).toBeInTheDocument()
  })

  it('narrows to medicines that need reordering', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/pharmacy')
    await medicineRows()
    await userEvent.click(screen.getByRole('button', { name: /^Needs reorder/ }))
    const names = (await medicineRows()).map((row) => row.dataset.medicine)
    expect(names).toEqual(['ceftriaxone', 'insulin-glargine', 'morphine', 'txa'])
  })

  it('searches by name', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/pharmacy')
    await medicineRows()
    await userEvent.type(screen.getByLabelText('Search medicines'), 'potass')
    expect((await medicineRows()).map((row) => row.dataset.medicine)).toEqual(['kcl'])
  })

  it('shows the batches behind a medicine', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/pharmacy')
    await medicineRows()
    const toggle = screen.getByRole('button', { name: 'Batches for Potassium chloride' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('KCL-2309')).toBeInTheDocument()
    expect(screen.getByText('KCL-2404')).toBeInTheDocument()
  })
})
