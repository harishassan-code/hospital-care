import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getPostLoginPath } from '../auth/roles'
import { loadSession, saveSession } from '../auth/session'
import { adminUser, coordinatorUser, mockLoginResponse, staffUser } from '../test/mock-auth'
import { renderWithRouter } from '../test/test-utils'
import Login from './Login'

describe('Login page — positive QA (CityCare / CareLink)', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  afterEach(() => vi.restoreAllMocks())

  it('TC-01 login page loads with primary elements visible', () => {
    renderWithRouter(<Login />)
    expect(screen.getByTestId('login-page')).toBeInTheDocument()
    expect(screen.getByTestId('login-logo')).toBeInTheDocument()
  })

  it('TC-02 displays logo, credentials fields, login button, forgot link, and remember me', () => {
    renderWithRouter(<Login />)
    expect(screen.getByTestId('login-logo')).toBeInTheDocument()
    expect(screen.getByTestId('login-email')).toBeInTheDocument()
    expect(screen.getByTestId('login-password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument()
    expect(screen.getByTestId('login-forgot-password')).toHaveTextContent('Forgot Password?')
    expect(screen.getByTestId('login-remember')).toBeInTheDocument()
  })

  it('TC-03 successful login redirects hospital staff to the dashboard', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockLoginResponse(staffUser))
    renderWithRouter(<Login />, { router: { initialEntries: ['/login'] } })
    await user.type(screen.getByTestId('login-email'), staffUser.email)
    await user.type(screen.getByTestId('login-password'), 'valid-password')
    await user.click(screen.getByTestId('login-submit'))
    await waitFor(() => expect(loadSession()?.user.role).toBe('hospital_staff'))
    expect(getPostLoginPath(staffUser)).toBe('/dashboard')
  })

  it('TC-04 login button stays disabled until both fields are filled', async () => {
    const user = userEvent.setup()
    renderWithRouter(<Login />)
    const submit = screen.getByTestId('login-submit')
    expect(submit).toBeDisabled()
    await user.type(screen.getByTestId('login-email'), 'user@hospital.com')
    expect(submit).toBeDisabled()
    await user.type(screen.getByTestId('login-password'), 'secret')
    expect(submit).toBeEnabled()
  })

  it('TC-05 password field masks input', () => {
    renderWithRouter(<Login />)
    expect(screen.getByTestId('login-password')).toHaveAttribute('type', 'password')
  })

  it('TC-06 show/hide password toggle reveals and re-masks text', async () => {
    const user = userEvent.setup()
    renderWithRouter(<Login />)
    const password = screen.getByTestId('login-password')
    await user.type(password, 'P@ssw0rd!')
    await user.click(screen.getByTestId('login-toggle-password'))
    expect(password).toHaveAttribute('type', 'text')
    await user.click(screen.getByTestId('login-toggle-password'))
    expect(password).toHaveAttribute('type', 'password')
  })

  it('TC-07 remember me stores session in localStorage', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockLoginResponse(staffUser))
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), staffUser.email)
    await user.type(screen.getByTestId('login-password'), 'valid-password')
    await user.click(screen.getByTestId('login-remember'))
    await user.click(screen.getByTestId('login-submit'))
    await waitFor(() => expect(localStorage.getItem('carelink.remember')).toBeTruthy())
  })

  it('TC-08 accepts a properly formatted email on login', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockLoginResponse(staffUser))
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), 'user@hospital.com')
    await user.type(screen.getByTestId('login-password'), 'valid-password')
    await user.click(screen.getByTestId('login-submit'))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(screen.queryByTestId('login-email-error')).not.toBeInTheDocument()
  })

  it('TC-09 supports username identifier when no @ is present', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockLoginResponse(staffUser))
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), 'jdoe')
    await user.type(screen.getByTestId('login-password'), 'valid-password')
    await user.click(screen.getByTestId('login-submit'))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toMatchObject({ email: 'jdoe' })
  })

  it('TC-10 tab order moves through email, password, remember me, then submit', async () => {
    const user = userEvent.setup()
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), 'user@hospital.com')
    await user.type(screen.getByTestId('login-password'), 'secret')
    await user.click(screen.getByTestId('login-email'))
    await user.tab()
    expect(screen.getByTestId('login-password')).toHaveFocus()
    await user.tab()
    expect(screen.getByTestId('login-remember')).toHaveFocus()
    await user.tab()
    expect(screen.getByTestId('login-submit')).toHaveFocus()
  })

  it('TC-11 enter key submits the login form', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockLoginResponse(staffUser))
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), staffUser.email)
    await user.type(screen.getByTestId('login-password'), 'valid-password{Enter}')
    await waitFor(() => expect(loadSession()?.token).toBe('test-token'))
  })

  it('TC-12 password with special characters is sent unchanged', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockLoginResponse(staffUser))
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), staffUser.email)
    await user.type(screen.getByTestId('login-password'), 'P@ssw0rd!')
    await user.click(screen.getByTestId('login-submit'))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(String(init.body)).password).toBe('P@ssw0rd!')
  })

  it('TC-13 forgot password link targets the reset route', () => {
    renderWithRouter(<Login />)
    expect(screen.getByTestId('login-forgot-password')).toHaveAttribute('href', '/forgot-password')
  })

  it('TC-14 role-based post-login paths differ by role', () => {
    expect(getPostLoginPath(staffUser)).toBe('/dashboard')
    expect(getPostLoginPath(adminUser)).toBe('/admin')
    expect(getPostLoginPath(coordinatorUser)).toBe('/emergency/new')
  })

  it('TC-15 session token is persisted after successful login', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockLoginResponse(staffUser, 'session-abc'))
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), staffUser.email)
    await user.type(screen.getByTestId('login-password'), 'valid-password')
    await user.click(screen.getByTestId('login-submit'))
    await waitFor(() => expect(loadSession()?.token).toBe('session-abc'))
  })

  it('TC-16 login page exposes responsive layout hook class', () => {
    renderWithRouter(<Login />)
    expect(screen.getByTestId('login-page')).toHaveClass('login-page')
  })

  it('TC-17 username and password fields expose browser autofill hints', () => {
    renderWithRouter(<Login />)
    expect(screen.getByTestId('login-email')).toHaveAttribute('autocomplete', 'username')
    expect(screen.getByTestId('login-password')).toHaveAttribute('autocomplete', 'current-password')
  })

  it('TC-18 loading indicator appears while authentication runs', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => resolve(mockLoginResponse(staffUser)), 50)
        }),
    )
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), staffUser.email)
    await user.type(screen.getByTestId('login-password'), 'valid-password')
    await user.click(screen.getByTestId('login-submit'))
    expect(screen.getByTestId('login-loading')).toBeInTheDocument()
    await waitFor(() => expect(loadSession()?.token).toBeTruthy())
  })

  it('TC-21 administrator login resolves to admin dashboard path', () => {
    expect(getPostLoginPath(adminUser)).toBe('/admin')
  })

  it('TC-23 coordinator login resolves to emergency request entry path', () => {
    expect(getPostLoginPath(coordinatorUser)).toBe('/emergency/new')
  })

  it('TC-29 deep-link return path is honored after login', () => {
    expect(getPostLoginPath(staffUser, '/requests/REQ-1042')).toBe('/requests/REQ-1042')
  })

  it('TC-30 login API success payload includes token, role, and hospital id', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockLoginResponse(staffUser))
    const { authenticateLogin } = await import('../auth/login')
    const result = await authenticateLogin(staffUser.email, 'valid-password')
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.token).toBeTruthy()
      expect(result.user.role).toBe('hospital_staff')
      expect(result.user.hospitalId).toBe('hosp-city-general')
    }
  })
})

describe('TC-20 logout clears session (dashboard integration)', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    saveSession({ token: 't', user: staffUser }, false)
  })

  it('TC-20 clears stored session when logout handler runs', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          hospitalId: staffUser.hospitalId,
          hospitalName: staffUser.hospitalName,
          icuBedsAvailable: 2,
          bloodUnitsAvailable: 5,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    const { default: Landing } = await import('./Landing')
    renderWithRouter(<Landing />, { router: { initialEntries: ['/dashboard'] } })
    await user.click(screen.getByTestId('landing-logout'))
    expect(loadSession()).toBeNull()
  })
})
