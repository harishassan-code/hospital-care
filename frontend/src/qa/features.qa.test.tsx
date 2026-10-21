/**
 * QA smoke: what the app actually ships today (public home, auth, staff RBAC, admin modules).
 */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppRoutes } from '../App'
import { hospital } from '../config/hospital'
import LandingPage from '../pages/LandingPage'
import LoginPage from '../pages/LoginPage'
import SignupPage from '../pages/SignupPage'
import { at } from '../test/clock'
import { samplePublicStatus } from '../test/fixtures/publicStatus'
import { mockApi, mockStaffApi, ok, fail, userFor } from '../test/mockApi'
import { renderStaff } from '../test/renderStaff'

const GENERIC = 'That email and password don’t match an account'

function Where() {
  return <p data-testid="where">{useLocation().pathname}</p>
}

function renderLogin(next?: string) {
  const url = next ? `/login?next=${encodeURIComponent(next)}` : '/login'
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/staff/*" element={<Where />} />
        <Route path="/" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  )
}

async function logIn(email: string, password: string) {
  await userEvent.type(screen.getByLabelText('Email'), email)
  await userEvent.type(screen.getByLabelText('Password'), password)
  await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})
afterEach(() => vi.restoreAllMocks())

describe('QA · public home', () => {
  it('shows hospital, wayfinding, log in link, live ER status', async () => {
    mockApi({ 'GET /public/status/': ok(samplePublicStatus(new Date())) })
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'Where do you need to go?' })).toBeInTheDocument()
    expect(screen.getAllByText(hospital.name).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Log in' })[0]).toHaveAttribute('href', '/login')
    expect((await screen.findAllByText(/min wait/)).length).toBeGreaterThan(0)
  })

  it('shows clear message when live status fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Live status isn’t available right now/)).toBeInTheDocument()
  })
})

describe('QA · sign in', () => {
  it('staff lands on workspace after good credentials', async () => {
    mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin()
    await logIn('nurse@demo.test', 'valid-password-1')
    expect(await screen.findByTestId('where')).toHaveTextContent('/staff')
  })

  it('patient lands on public home', async () => {
    mockApi({ 'POST /auth/login/': ok(userFor('patient')) })
    renderLogin()
    await logIn('patient@demo.test', 'valid-password-1')
    expect(await screen.findByTestId('where')).toHaveTextContent('/')
  })

  it('empty submit shows field errors and sends nothing', async () => {
    const fetchMock = mockApi({})
    renderLogin()
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(screen.getByText('Enter your email address')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('wrong password shows generic message', async () => {
    mockApi({ 'POST /auth/login/': fail(401) })
    renderLogin()
    await logIn('nurse@demo.test', 'wrong-password-1')
    expect(await screen.findByRole('alert')).toHaveTextContent(GENERIC)
  })

  it('lockout after too many failures', async () => {
    mockApi({ 'POST /auth/login/': fail(429) })
    renderLogin()
    await logIn('nurse@demo.test', 'wrong-password-1')
    expect(await screen.findByRole('alert')).toHaveTextContent(/Too many failed sign-in attempts/)
  })

  it('returns to internal page after sign-in via next=', async () => {
    mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin('/staff/beds')
    await logIn('nurse@demo.test', 'valid-password-1')
    expect(await screen.findByTestId('where')).toHaveTextContent('/staff/beds')
  })

  it('ignores external next= URLs', async () => {
    mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin('https://evil.example/phish')
    await logIn('nurse@demo.test', 'valid-password-1')
    expect(await screen.findByTestId('where')).toHaveTextContent('/staff')
  })
})

describe('QA · patient sign up', () => {
  it('tells staff not to use self-service sign up', () => {
    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Your administrator creates staff accounts/)).toBeInTheDocument()
  })
})

describe('QA · staff workspace', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(at('15:00'))
  })
  afterEach(() => vi.useRealTimers())

  it('signed-out user cannot open workspace', async () => {
    mockStaffApi({ role: null })
    renderStaff('/staff')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('nurse nav hides blood bank', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    const labels = within(screen.getByRole('navigation', { name: 'Staff' }))
      .getAllByRole('link')
      .map((a) => a.textContent)
    expect(labels).not.toContain('Blood bank')
  })

  it('nurse cannot open blood bank by URL', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/blood')
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
  })

  it('admin sees hospitals and users in nav', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    const labels = within(screen.getByRole('navigation', { name: 'Staff' }))
      .getAllByRole('link')
      .map((a) => a.textContent)
    expect(labels).toEqual(expect.arrayContaining(['Hospitals', 'Users and roles']))
  })

  it('sign out returns to sign in', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff')
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('admin can open hospital network list', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals')
    expect(await screen.findByRole('table', { name: 'Hospitals in the network' })).toBeInTheDocument()
  })

  it('admin can open users and roles', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/users')
    expect(await screen.findByRole('table', { name: 'Users and their roles' })).toBeInTheDocument()
  })
})

describe('QA · app shell', () => {
  it('unknown route shows not found with link home', () => {
    render(
      <MemoryRouter initialEntries={['/nope']}>
        <AppRoutes />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'This page doesn’t exist' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to/i })).toHaveAttribute('href', '/')
  })
})
