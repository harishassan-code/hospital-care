import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

async function fillValid() {
  await userEvent.type(await screen.findByLabelText('Name'), 'Northside Hospital')
  await userEvent.type(screen.getByLabelText('Address'), 'North Nazimabad, Karachi')
  await userEvent.type(screen.getByLabelText('Latitude'), '24.9420')
  await userEvent.type(screen.getByLabelText('Longitude'), '67.0347')
}

describe('HospitalFormPage (story 1.3 Hospital registration and capability profile)', () => {
  it('explains every missing field and moves focus to the first one', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/new')
    await userEvent.click(await screen.findByRole('button', { name: 'Save hospital' }))
    expect(screen.getByLabelText('Name')).toHaveFocus()
    expect(screen.getByLabelText('Name')).toHaveAccessibleDescription('Enter the hospital’s name')
    expect(screen.getByLabelText('Latitude')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('Enter the longitude')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('The hospital wasn’t saved. Fix the 4 fields marked above.')
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('refuses coordinates outside the globe before sending', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/new')
    await fillValid()
    await userEvent.clear(screen.getByLabelText('Latitude'))
    await userEvent.type(screen.getByLabelText('Latitude'), '124')
    await userEvent.click(screen.getByRole('button', { name: 'Save hospital' }))
    expect(screen.getByLabelText('Latitude')).toHaveFocus()
    expect(screen.getByText('The latitude must be between -90 and 90')).toBeInTheDocument()
  })

  it('registers a blood bank with capabilities and opens its page', async () => {
    const { fetchMock, hospitals } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/new')
    await fillValid()
    await userEvent.click(screen.getByRole('radio', { name: 'Blood bank' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Trauma centre' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save hospital' }))
    expect(await screen.findByRole('heading', { name: 'Northside Hospital' })).toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      name: 'Northside Hospital',
      type: 'bloodBank',
      address: 'North Nazimabad, Karachi',
      latitude: 24.942,
      longitude: 67.0347,
      phone: '',
      isActive: true,
      capabilities: ['trauma'],
    })
    expect(hospitals).toHaveLength(4)
    expect(screen.getByRole('list', { name: 'Capabilities' })).toHaveTextContent('Trauma centre')
  })

  it('shows the server’s reason next to the field it is about', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/new')
    await fillValid()
    await userEvent.clear(screen.getByLabelText('Name'))
    await userEvent.type(screen.getByLabelText('Name'), 'seaview hospital')
    await userEvent.click(screen.getByRole('button', { name: 'Save hospital' }))
    expect(await screen.findByText('A hospital with this name is already registered.')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveFocus()
    expect(screen.getByRole('alert')).toHaveTextContent('The hospital wasn’t saved. Fix the fields marked above.')
  })

  it('edits a hospital, deactivates it, and keeps unchanged fields', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/2/edit')
    expect(await screen.findByLabelText('Name')).toHaveValue('Seaview Hospital')
    expect(screen.getByRole('checkbox', { name: 'Neonatal ICU' })).toBeChecked()
    await userEvent.click(screen.getByRole('checkbox', { name: /Active/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Save hospital' }))
    expect(await screen.findByText('Deactivated')).toBeInTheDocument()
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH')
    expect(new URL(String(patch?.[0])).pathname).toBe('/api/hospitals/2/')
    expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({ name: 'Seaview Hospital', isActive: false, capabilities: ['nicu'] })
  })

  it.each(['/staff/hospitals/new', '/staff/hospitals/1/edit'])('blocks %s for roles that can only view hospitals', async (path) => {
    mockStaffApi({ role: 'nurse' })
    renderStaff(path)
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save hospital' })).toBeNull()
  })
})
