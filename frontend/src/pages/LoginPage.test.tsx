import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import LoginPage from './LoginPage'

const renderPage = () =>
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )

afterEach(() => vi.restoreAllMocks())

async function submitWith(email: string, password: string) {
  await userEvent.type(screen.getByLabelText('Email'), email)
  await userEvent.type(screen.getByLabelText('Password'), password)
  await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
}

describe('LoginPage', () => {
  it('shows field errors and focuses the first invalid field', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(screen.getByText('Enter your email address')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveFocus()
  })

  it('tells the user when the credentials are wrong', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }))
    renderPage()
    await submitWith('sara@example.com', 'wrong-password')
    expect(await screen.findByRole('alert')).toHaveTextContent('That email and password don’t match an account')
  })

  it('explains when the server is unreachable', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    renderPage()
    await submitWith('sara@example.com', 'anything-1')
    expect(await screen.findByRole('alert')).toHaveTextContent('The hospital’s server didn’t respond')
  })

  it('reveals password help', async () => {
    renderPage()
    const toggle = screen.getByRole('button', { name: 'Forgot your password?' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText(/Ask the front desk to reset it/)).toBeVisible()
  })

  it('links new patients to sign up', () => {
    renderPage()
    expect(screen.getByRole('link', { name: 'Create an account' })).toHaveAttribute('href', '/signup')
  })
})
