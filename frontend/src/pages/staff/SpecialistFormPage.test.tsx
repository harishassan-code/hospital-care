import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SAMPLE_NOON } from '../../test/fixtures/specialists'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(SAMPLE_NOON))
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const optionsOf = (select: HTMLElement) => within(select).getAllByRole('option').map((option) => option.textContent)

describe('SpecialistFormPage (story #61)', () => {
  it('lists a specialist at the nurse’s own hospital, and shows the new profile', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/new')
    expect(optionsOf(await screen.findByLabelText('Hospital'))).toEqual(['CityCare General Hospital'])
    await userEvent.type(screen.getByLabelText('Name'), 'Dr. Sara Ali')
    await userEvent.type(screen.getByLabelText('Specialty'), 'Neurology')
    await userEvent.click(screen.getByRole('button', { name: 'Add specialist' }))
    expect(await screen.findByRole('heading', { name: 'Dr. Sara Ali' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/specialists\/$/),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'Dr. Sara Ali', specialty: 'Neurology', hospitalId: 1 }),
      }),
    )
  })

  it('lets an admin list at any active hospital, but not at a deactivated one', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/specialists/new')
    expect(optionsOf(await screen.findByLabelText('Hospital'))).toEqual(['CityCare General Hospital', 'Seaview Hospital'])
  })

  it('asks for the name and the specialty', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/new')
    await userEvent.click(await screen.findByRole('button', { name: 'Add specialist' }))
    expect(screen.getByText('Enter the name, e.g. Dr. Ayesha Khan.')).toBeInTheDocument()
    expect(screen.getByText('Enter the specialty, e.g. Cardiology.')).toBeInTheDocument()
  })

  it('shows the server’s answer when the name is already listed at the hospital', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/new')
    await userEvent.type(await screen.findByLabelText('Name'), 'Dr. Ayesha Khan')
    await userEvent.type(screen.getByLabelText('Specialty'), 'Cardiology')
    await userEvent.click(screen.getByRole('button', { name: 'Add specialist' }))
    expect(await screen.findByText('A specialist with this name is already listed at this hospital.')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveAttribute('aria-invalid', 'true')
  })

  it('tells the user when the hospital didn’t answer, and keeps what they typed', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    const served = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input, init) =>
      init?.method === 'POST' ? Promise.reject(new TypeError('Failed to fetch')) : served(input, init),
    )
    renderStaff('/staff/specialists/new')
    await userEvent.type(await screen.findByLabelText('Name'), 'Dr. Sara Ali')
    await userEvent.type(screen.getByLabelText('Specialty'), 'Neurology')
    await userEvent.click(screen.getByRole('button', { name: 'Add specialist' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The hospital’s system didn’t respond, so nothing was saved. Try again.')
    expect(screen.getByLabelText('Name')).toHaveValue('Dr. Sara Ali')
  })

  it('edits a profile: it is filled in, and the change is saved and shown', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/1/edit')
    expect(await screen.findByLabelText('Name')).toHaveValue('Dr. Ayesha Khan')
    expect(screen.getByLabelText('Specialty')).toHaveValue('Cardiology')
    expect(screen.getByText(/A specialist stays at the hospital they were listed at/)).toBeInTheDocument()
    await userEvent.clear(screen.getByLabelText('Specialty'))
    await userEvent.type(screen.getByLabelText('Specialty'), 'Heart surgery')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByRole('heading', { name: 'Dr. Ayesha Khan' })).toBeInTheDocument()
    expect(screen.getByText('Heart surgery')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/specialists\/1\/$/),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ name: 'Dr. Ayesha Khan', specialty: 'Heart surgery', isActive: true }),
      }),
    )
  })

  it('reactivates a deactivated profile from the edit form', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/specialists/4/edit')
    const active = await screen.findByRole('checkbox', { name: 'Active: on the list, and can be on call' })
    expect(active).not.toBeChecked()
    await userEvent.click(active)
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('Active')).toBeInTheDocument()
    expect(screen.queryByText('Deactivated')).not.toBeInTheDocument()
  })

  it('shows the server’s refusal when a nurse edits another hospital’s specialist', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists/3/edit')
    await userEvent.click(await screen.findByRole('button', { name: 'Save changes' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('You can only change specialists at your own hospital.')
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/specialists/3/'), expect.objectContaining({ method: 'PATCH' }))
  })

  it('keeps a doctor out of the editor', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/specialists/new')
    expect(await screen.findByText(/can’t open the specialist editor/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add specialist' })).not.toBeInTheDocument()
  })
})
