/**
 * QA smoke: what the app actually ships today (public home, auth, staff RBAC, admin modules).
 */
import { cleanup, render, screen, within } from '@testing-library/react'
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

  it('doctor signs in straight to emergency case entry', async () => {
    // There is no coordinator role yet (#9); doctors open emergency cases (#30).
    mockStaffApi({ role: 'doctor' })
    render(
      <MemoryRouter initialEntries={['/login?next=%2Fstaff%2Femergencies']}>
        <AppRoutes />
      </MemoryRouter>,
    )
    await logIn('doctor@demo.test', 'valid-password-1')
    await userEvent.click(await screen.findByRole('button', { name: 'New case' }))
    expect(screen.getByRole('heading', { name: 'Step 1 of 3: Case' })).toHaveFocus()
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

  it('doctor nav links to transfers; pharmacist nav does not', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    const doctorLabels = within(screen.getByRole('navigation', { name: 'Staff' }))
      .getAllByRole('link')
      .map((a) => a.textContent)
    expect(doctorLabels).toEqual(expect.arrayContaining(['Transfers']))
    expect(screen.getByRole('link', { name: 'Transfers' })).toHaveAttribute('href', '/staff/transfers')
  })

  it('pharmacist nav hides transfers', async () => {
    mockStaffApi({ role: 'pharmacist' })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    const labels = within(screen.getByRole('navigation', { name: 'Staff' }))
      .getAllByRole('link')
      .map((a) => a.textContent)
    expect(labels).not.toContain('Transfers')
  })

  it.each(['nurse', 'doctor'] as const)('%s nav links to ambulances', async (role) => {
    mockStaffApi({ role })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    const labels = within(screen.getByRole('navigation', { name: 'Staff' }))
      .getAllByRole('link')
      .map((a) => a.textContent)
    expect(labels).toEqual(expect.arrayContaining(['Ambulances']))
    expect(screen.getByRole('link', { name: 'Ambulances' })).toHaveAttribute('href', '/staff/ambulances')
  })

  it.each(['bloodBank', 'pharmacist'] as const)('%s nav hides ambulances', async (role) => {
    mockStaffApi({ role })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    const labels = within(screen.getByRole('navigation', { name: 'Staff' }))
      .getAllByRole('link')
      .map((a) => a.textContent)
    expect(labels).not.toContain('Ambulances')
  })

  it('nurse can open ambulances', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/ambulances')
    expect(await screen.findByRole('table', { name: 'Ambulances' })).toBeInTheDocument()
  })

  it('nurse cannot open blood bank by URL', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/blood')
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
  })

  it('blood bank nav links to donors; doctor and nurse nav hide them', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    const bloodBankLabels = within(screen.getByRole('navigation', { name: 'Staff' }))
      .getAllByRole('link')
      .map((a) => a.textContent)
    expect(bloodBankLabels).toEqual(expect.arrayContaining(['Donors']))
    expect(screen.getByRole('link', { name: 'Donors' })).toHaveAttribute('href', '/staff/donors')
    cleanup()

    for (const role of ['doctor', 'nurse'] as const) {
      mockStaffApi({ role })
      renderStaff('/staff')
      await screen.findByRole('navigation', { name: 'Staff' })
      const labels = within(screen.getByRole('navigation', { name: 'Staff' }))
        .getAllByRole('link')
        .map((a) => a.textContent)
      expect(labels).not.toContain('Donors')
      cleanup()
    }
  })

  it('doctor cannot open donors by URL', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/donors')
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

  it('admin sees the city command centre in nav; nurse does not', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    expect(screen.getByRole('link', { name: 'City command centre' })).toHaveAttribute('href', '/staff/command-centre')
  })

  it('nurse nav hides the city command centre', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    const labels = within(screen.getByRole('navigation', { name: 'Staff' }))
      .getAllByRole('link')
      .map((a) => a.textContent)
    expect(labels).not.toContain('City command centre')
  })

  it('nurse cannot open the city command centre by URL', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/command-centre')
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
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

describe('QA · audit log (B10, #56)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(at('15:00'))
  })
  afterEach(() => vi.useRealTimers())

  const navLabels = () => within(screen.getByRole('navigation', { name: 'Staff' })).getAllByRole('link').map((a) => a.textContent)

  it('admin nav links to the audit log', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    expect(navLabels()).toEqual(expect.arrayContaining(['Audit log']))
    expect(screen.getByRole('link', { name: 'Audit log' })).toHaveAttribute('href', '/staff/audit')
  })

  it.each(['doctor', 'nurse', 'bloodBank', 'pharmacist'] as const)('%s nav has no audit log', async (role) => {
    mockStaffApi({ role })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    expect(navLabels()).not.toContain('Audit log')
  })

  it('admin can open the audit log', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/audit')
    expect(await screen.findByRole('table', { name: 'Audit entries' })).toBeInTheDocument()
  })
})

describe('QA · alerts (B07, #53)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(at('15:00'))
  })
  afterEach(() => vi.useRealTimers())

  const navLabels = () => within(screen.getByRole('navigation', { name: 'Staff' })).getAllByRole('link').map((a) => a.textContent)

  it.each(['admin', 'doctor', 'nurse', 'bloodBank', 'pharmacist'] as const)('%s nav links to the alerts page', async (role) => {
    mockStaffApi({ role })
    renderStaff('/staff')
    await screen.findByRole('navigation', { name: 'Staff' })
    expect(navLabels()).toEqual(expect.arrayContaining(['Alerts']))
    expect(screen.getByRole('link', { name: 'Alerts' })).toHaveAttribute('href', '/staff/alerts')
    expect(navLabels()[1]).toBe('Alerts')
  })

  it.each(['admin', 'doctor', 'nurse', 'bloodBank', 'pharmacist'] as const)('%s can open the alerts page', async (role) => {
    mockStaffApi({ role, notifications: [] })
    renderStaff('/staff/alerts')
    expect(await screen.findByRole('region', { name: 'Your alerts' })).toBeInTheDocument()
    expect(await screen.findByText('No notifications yet.')).toBeInTheDocument()
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
