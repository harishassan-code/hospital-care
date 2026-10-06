import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi, ok, userFor } from '../test/mockApi'
import LoginPage from './LoginPage'

function Where() {
  return <p>at {useLocation().pathname}</p>
}

/** The login page inside a router, so we can see where a successful login lands. */
const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  )

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

  it.each([
    ['staff', 'nurse', '/login', 'at /staff'],
    ['staff, back where they were going', 'nurse', '/login?next=%2Fstaff%2Fbeds', 'at /staff/beds'],
    ['patients, to the home page', 'patient', '/login?next=%2Fstaff', 'at /'],
    ['staff, ignoring a link to another site', 'admin', '/login?next=%2F%2Fevil.example', 'at /staff'],
    ['staff, ignoring a full URL', 'admin', '/login?next=https%3A%2F%2Fevil.example', 'at /staff'],
  ] as const)('signs in %s', async (_case, role, url, landing) => {
    mockApi({ 'POST /auth/login/': ok(userFor(role)) })
    renderAt(url)
    await submitWith('someone@example.com', 'right-password-1')
    expect(await screen.findByText(landing)).toBeInTheDocument()
  })

  it('links new patients to sign up', () => {
    renderPage()
    expect(screen.getByRole('link', { name: 'Create an account' })).toHaveAttribute('href', '/signup')
  })
})
