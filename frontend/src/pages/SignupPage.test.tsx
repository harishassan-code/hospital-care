import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SignupPage from './SignupPage'

const renderPage = () =>
  render(
    <MemoryRouter>
      <SignupPage />
    </MemoryRouter>,
  )

afterEach(() => vi.restoreAllMocks())

async function fillValidForm() {
  await userEvent.type(screen.getByLabelText('Full name'), 'Sara Ahmed')
  await userEvent.type(screen.getByLabelText('Email'), 'sara@example.com')
  await userEvent.type(screen.getByLabelText('Password'), 'blood-bank-7')
  await userEvent.type(screen.getByLabelText('Confirm password'), 'blood-bank-7')
  await userEvent.click(screen.getByRole('checkbox'))
}

describe('SignupPage', () => {
  it('tells staff they do not sign up here', () => {
    renderPage()
    expect(screen.getByText(/Your administrator creates staff accounts/)).toBeInTheDocument()
  })

  it('validates mismatched passwords and unchecked terms', async () => {
    renderPage()
    await userEvent.type(screen.getByLabelText('Password'), 'blood-bank-7')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'blood-bank-8')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByText('Passwords don’t match')).toBeInTheDocument()
    expect(screen.getByText('Agree to the terms to create an account')).toBeInTheDocument()
    expect(screen.getByLabelText('Full name')).toHaveFocus()
  })

  it('reports an email that is already registered', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 409 }))
    renderPage()
    await fillValidForm()
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('An account with this email already exists')
  })

  it('confirms success and points to log in', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 201 }))
    renderPage()
    await fillValidForm()
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Account created. You can now log in.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
  })
})
