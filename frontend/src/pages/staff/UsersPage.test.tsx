import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

const row = async (name: string) => (await screen.findByRole('cell', { name })).closest('tr') as HTMLElement

describe('UsersPage (story 1.2 Role management)', () => {
  it('lists every account with its hospital and role', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/users')
    expect(await screen.findByRole('table', { name: 'Users and their roles' })).toBeInTheDocument()
    expect(within(await row('Hina Javed')).getByRole('combobox', { name: 'Role for Hina Javed' })).toHaveValue('nurse')
    expect(within(await row('Hina Javed')).getByText('CityCare General Hospital')).toBeInTheDocument()
    expect(within(await row('Root Admin')).getByText('All hospitals')).toBeInTheDocument()
    expect(screen.getByText('5 accounts')).toBeInTheDocument()
  })

  it('changes a role through the API and announces it', async () => {
    const { fetchMock, users } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/users')
    const nurse = await row('Hina Javed')
    const save = within(nurse).getByRole('button', { name: 'Save role for Hina Javed' })
    expect(save).toBeDisabled()
    await userEvent.selectOptions(within(nurse).getByRole('combobox'), 'doctor')
    await userEvent.click(save)
    expect(await screen.findByText('Hina Javed is now Doctor. The change applies on their next page load.')).toHaveAttribute(
      'aria-live',
      'polite',
    )
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH')
    expect(new URL(String(patch?.[0])).pathname).toBe('/api/users/2/')
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ role: 'doctor' })
    expect(users.find((u) => u.id === 2)?.role).toBe('doctor')
  })

  it('shows locked accounts as text, with the reason', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/users')
    expect(within(await row('Sadia Admin')).getByText('(your account)')).toBeInTheDocument()
    expect(within(await row('Root Admin')).getByText('(superuser: change in Django admin)')).toBeInTheDocument()
    expect(within(await row('Sadia Admin')).queryByRole('combobox')).toBeNull()
  })

  it('reports a refused change and puts the old role back', async () => {
    const { users } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/users')
    const nurse = await row('Hina Javed')
    users[1].roleLocked = true // the server starts refusing after the page has loaded
    await userEvent.selectOptions(within(nurse).getByRole('combobox'), 'admin')
    await userEvent.click(within(nurse).getByRole('button', { name: /Save/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('You can’t change your own role.')
    expect(within(nurse).getByRole('combobox')).toHaveValue('nurse')
  })

  it('says so plainly when the list cannot be loaded', async () => {
    mockStaffApi({ role: 'admin', networkDown: true })
    renderStaff('/staff/users')
    expect(await screen.findByText(/hospital’s system didn’t respond/)).toBeInTheDocument()
  })

  it('is closed to every other role, before any user data is requested', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/users')
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname)).not.toContain('/api/users/')
  })
})
