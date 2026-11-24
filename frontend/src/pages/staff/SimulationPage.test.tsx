import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

describe('Simulation panel (B21)', () => {
  it('is in the CityCare admin’s menu and nobody else’s', async () => {
    mockStaffApi({ role: 'admin', network: true })
    renderStaff('/staff')
    const nav = await screen.findByRole('navigation', { name: 'Staff' })
    expect(within(nav).getByRole('link', { name: /Simulation/ })).toHaveAttribute('href', '/staff/simulation')
  })

  it('is hidden from a hospital’s admin, who can’t open it', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/simulation')
    const nav = await screen.findByRole('navigation', { name: 'Staff' })
    expect(within(nav).queryByRole('link', { name: /Simulation/ })).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
    expect(screen.getByText(/Only the CityCare admin, who works for the whole network rather than one hospital, can open Simulation/)).toBeInTheDocument()
  })

  it('pauses, resumes and changes speed', async () => {
    mockStaffApi({ role: 'admin', network: true })
    renderStaff('/staff/simulation')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Pause' }))
    expect(await screen.findByRole('button', { name: 'Resume' })).toBeInTheDocument()
    expect(screen.getByText('Paused the city clock.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Resume' }))
    await user.click(await screen.findByRole('button', { name: '10×' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '10×' })).toHaveAttribute('aria-pressed', 'true'))
    expect(screen.getByRole('button', { name: 'Real time (1×)' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('fast-forwards a day with a progress bar until it is done', async () => {
    mockStaffApi({ role: 'admin', network: true })
    renderStaff('/staff/simulation')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: '+ 1 day' }))
    await waitFor(() => expect(screen.getByText('Fast-forwarded a day.')).toBeInTheDocument())
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '+ 1 week' })).toBeEnabled()
  })

  it('picks a scenario and sets off a mass-casualty event', async () => {
    mockStaffApi({ role: 'admin', network: true })
    renderStaff('/staff/simulation')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('radio', { name: /Flu season/ }))
    await waitFor(() => expect(screen.getByRole('radio', { name: /Flu season/ })).toBeChecked())
    await user.click(screen.getByRole('button', { name: 'Set off a mass-casualty event' }))
    expect(await screen.findByText(/Patients are going to Bahadurabad Medical Centre/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'End it now' }))
    expect(await screen.findByRole('button', { name: 'Set off a mass-casualty event' })).toBeInTheDocument()
  })

  it('lists what the simulation did lately', async () => {
    mockStaffApi({ role: 'admin', network: true })
    renderStaff('/staff/simulation')
    const events = await screen.findByRole('region', { name: 'What happened lately' })
    expect(within(events).getByText(/a triage 1 patient arrived/)).toBeInTheDocument()
  })
})
