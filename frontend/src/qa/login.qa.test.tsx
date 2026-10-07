/**
 * QA test cases for the sign-in flow, from the QA sheet (TC-*, LOGIN-N*) by Muhammad Hassaan (PR #70),
 * rewritten against the real login page and API. Each test name starts with its QA id. Cases that changed
 * meaning are marked ADAPTED; the reasons are in docs/testing/authentication-test-report.md.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppRoutes } from '../App'
import { mockApi, ok, fail, userFor } from '../test/mockApi'
import { samplePublicStatus } from '../test/fixtures/publicStatus'
import LoginPage from '../pages/LoginPage'

const GENERIC = 'That email and password don’t match an account'

function Where() {
  return <p>landed on {useLocation().pathname}</p>
}

function renderLogin(url = '/login') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  )
}

const email = () => screen.getByLabelText('Email')
const password = () => screen.getByLabelText('Password')
const submit = () => screen.getByRole('button', { name: 'Log in' })
const posts = (fetchMock: ReturnType<typeof mockApi>) => fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')

async function signIn(address: string, secret: string) {
  await userEvent.type(email(), address)
  await userEvent.type(password(), secret)
  await userEvent.click(submit())
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})
afterEach(() => vi.restoreAllMocks())

describe('Sign-in: positive cases (TC)', () => {
  it('TC-01 the site opens on the public page, which links to sign-in', () => {
    mockApi({ 'GET /public/status/': ok(samplePublicStatus(new Date())) })
    render(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Where do you need to go?' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Log in' })[0]).toHaveAttribute('href', '/login')
  })

  it('TC-01 the login page loads with its heading and form', () => {
    renderLogin()
    expect(screen.getByRole('heading', { level: 1, name: 'Sign in' })).toBeInTheDocument()
    expect(submit()).toBeInTheDocument()
  })

  it('TC-02 shows the hospital name, both fields, the Log in button and password help (ADAPTED: no "remember me")', () => {
    renderLogin()
    expect(screen.getByRole('link', { name: /Northgate General Hospital/ })).toHaveAttribute('href', '/')
    expect(email()).toBeInTheDocument()
    expect(password()).toBeInTheDocument()
    expect(submit()).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Forgot your password?' })).toBeInTheDocument()
    expect(screen.queryByLabelText(/remember me/i)).toBeNull()
  })

  it('TC-03 a successful staff sign-in opens the staff workspace', async () => {
    mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin()
    await signIn('nurse@hospital.test', 'valid-password-1')
    expect(await screen.findByText('landed on /staff')).toBeInTheDocument()
  })

  it('TC-04 (ADAPTED) the button stays usable; an empty form explains what is missing and sends nothing', async () => {
    const fetchMock = mockApi({})
    renderLogin()
    expect(submit()).toBeEnabled()
    await userEvent.click(submit())
    expect(screen.getByText('Enter your email address')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('TC-05 / LOGIN-N11 the password is masked by default', () => {
    renderLogin()
    expect(password()).toHaveAttribute('type', 'password')
  })

  it('TC-06 Show reveals the password and Hide masks it again', async () => {
    renderLogin()
    await userEvent.type(password(), 'P@ssw0rd!')
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(password()).toHaveAttribute('type', 'text')
    await userEvent.click(screen.getByRole('button', { name: 'Hide password' }))
    expect(password()).toHaveAttribute('type', 'password')
  })

  it('TC-07 / TC-15 (ADAPTED) the session is a server cookie: nothing is stored in the browser', async () => {
    const fetchMock = mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin()
    await signIn('nurse@hospital.test', 'valid-password-1')
    await screen.findByText('landed on /staff')
    expect(posts(fetchMock)[0][1]?.credentials).toBe('include')
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it('TC-08 a properly formatted email is accepted and sent', async () => {
    const fetchMock = mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin()
    await signIn('user@hospital.test', 'valid-password-1')
    await screen.findByText('landed on /staff')
    expect(posts(fetchMock)).toHaveLength(1)
    expect(screen.queryByText(/Enter an email like/)).toBeNull()
  })

  it('TC-09 (ADAPTED) sign-in uses email only: a username without @ is refused before sending', async () => {
    const fetchMock = mockApi({})
    renderLogin()
    await signIn('jdoe', 'valid-password-1')
    expect(screen.getByText('Enter an email like name@example.com')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('TC-10 (ADAPTED) Tab moves through email, password, Show, password help, then Log in', async () => {
    renderLogin()
    await userEvent.click(email())
    await userEvent.tab()
    expect(password()).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Show password' })).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Forgot your password?' })).toHaveFocus()
    await userEvent.tab()
    expect(submit()).toHaveFocus()
  })

  it('TC-11 pressing Enter in the password field submits the form', async () => {
    const fetchMock = mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin()
    await userEvent.type(email(), 'nurse@hospital.test')
    await userEvent.type(password(), 'valid-password-1{Enter}')
    expect(await screen.findByText('landed on /staff')).toBeInTheDocument()
    expect(posts(fetchMock)).toHaveLength(1)
  })

  it('TC-12 / LOGIN-N12 the password is sent exactly as typed; the email is trimmed', async () => {
    const fetchMock = mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin()
    await signIn('  Nurse@Hospital.test  ', ' P@ss w0rd!#$% ')
    await screen.findByText('landed on /staff')
    expect(JSON.parse(String(posts(fetchMock)[0][1]?.body))).toEqual({
      email: 'Nurse@Hospital.test',
      password: ' P@ss w0rd!#$% ',
    })
  })

  it('TC-13 (ADAPTED) "Forgot your password?" explains how to get it reset', async () => {
    renderLogin()
    await userEvent.click(screen.getByRole('button', { name: 'Forgot your password?' }))
    expect(screen.getByText(/Ask the front desk to reset it/)).toBeVisible()
  })

  it.each(['admin', 'doctor', 'nurse', 'bloodBank', 'pharmacist'] as const)(
    'TC-14 / TC-21 (ADAPTED) %s signs in to the staff workspace',
    async (role) => {
      mockApi({ 'POST /auth/login/': ok(userFor(role)) })
      renderLogin()
      await signIn(`${role}@hospital.test`, 'valid-password-1')
      expect(await screen.findByText('landed on /staff')).toBeInTheDocument()
    },
  )

  it('TC-14 (ADAPTED) a patient signs in to the public home page', async () => {
    mockApi({ 'POST /auth/login/': ok(userFor('patient')) })
    renderLogin()
    await signIn('patient@hospital.test', 'valid-password-1')
    expect(await screen.findByText('landed on /')).toBeInTheDocument()
  })

  it('TC-17 the fields carry autofill hints for password managers', () => {
    renderLogin()
    expect(email()).toHaveAttribute('autocomplete', 'username')
    expect(password()).toHaveAttribute('autocomplete', 'current-password')
  })

  it('TC-18 the button shows progress and can’t be pressed twice while signing in', async () => {
    let answer: (value: Response) => void = () => {}
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise((resolve) => (answer = resolve)))
    renderLogin()
    await signIn('nurse@hospital.test', 'valid-password-1')
    const busy = screen.getByRole('button', { name: 'Logging in…' })
    expect(busy).toBeDisabled()
    answer(new Response(JSON.stringify(userFor('nurse')), { status: 200 }))
    expect(await screen.findByText('landed on /staff')).toBeInTheDocument()
  })

  it.todo('TC-23 coordinator signs in to emergency request entry (emergency requests are planned for Sprint 5)')

  it('TC-29 after sign-in, staff return to the page they asked for', async () => {
    mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin('/login?next=%2Fstaff%2Fbeds')
    await signIn('nurse@hospital.test', 'valid-password-1')
    expect(await screen.findByText('landed on /staff/beds')).toBeInTheDocument()
  })

  it('TC-29 the return page must be on this site (no redirect to another website)', async () => {
    mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin('/login?next=https%3A%2F%2Fevil.example%2Fsteal')
    await signIn('nurse@hospital.test', 'valid-password-1')
    expect(await screen.findByText('landed on /staff')).toBeInTheDocument()
  })

  it('TC-30 (ADAPTED) the login API returns the user and role; the session itself is a cookie, not a token', async () => {
    const { login } = await import('../api/auth')
    mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    const user = await login({ email: 'nurse@hospital.test', password: 'valid-password-1' })
    expect(user).toMatchObject({ role: 'nurse', isStaff: true })
    expect(user).not.toHaveProperty('token')
  })
})

describe('Sign-in: negative cases (LOGIN-N)', () => {
  it.each([
    ['LOGIN-N01 an unknown email', 'unknown@hospital.test'],
    ['LOGIN-N02 a wrong password', 'nurse@hospital.test'],
  ])('%s gets the same generic message', async (_case, address) => {
    mockApi({ 'POST /auth/login/': fail(401, { detail: 'nope' }) })
    renderLogin()
    await signIn(address, 'wrong-password-1')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(GENERIC)
    expect(alert.textContent).not.toMatch(/wrong password|incorrect password|no account/i)
  })

  it('LOGIN-N03 after too many failed attempts the account is locked for 15 minutes', async () => {
    mockApi({ 'POST /auth/login/': fail(429) })
    renderLogin()
    await signIn('nurse@hospital.test', 'wrong-password-1')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Too many failed sign-in attempts. Wait 15 minutes, or ask your hospital administrator to reset your password.',
    )
  })

  it('LOGIN-N04 an SQL-injection string is refused as a malformed email before reaching the server', async () => {
    const fetchMock = mockApi({})
    renderLogin()
    await signIn("' OR '1'='1", "admin'--")
    expect(screen.getByText('Enter an email like name@example.com')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('LOGIN-N05 a script typed into the form is shown as plain text, never run', async () => {
    renderLogin()
    await userEvent.type(email(), '<script>window.__xss = 1</script>')
    await userEvent.click(submit())
    expect(screen.getByText('Enter an email like name@example.com')).toBeInTheDocument()
    expect(document.querySelectorAll('main script')).toHaveLength(0)
    expect((window as unknown as { __xss?: number }).__xss).toBeUndefined()
  })

  it('LOGIN-N06 empty email, empty password, or both, are each blocked before sending', async () => {
    const fetchMock = mockApi({})
    renderLogin()
    await userEvent.click(submit())
    expect(screen.getByText('Enter your email address')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    await userEvent.type(email(), 'nurse@hospital.test')
    await userEvent.click(submit())
    expect(screen.queryByText('Enter your email address')).toBeNull()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    await userEvent.clear(email())
    await userEvent.type(password(), 'valid-password-1')
    await userEvent.click(submit())
    expect(screen.getByText('Enter your email address')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('LOGIN-N07 (ADAPTED) a deactivated account gets the generic message (the account isn’t confirmed to exist)', async () => {
    mockApi({ 'POST /auth/login/': fail(401, { detail: 'inactive' }) })
    renderLogin()
    await signIn('former@hospital.test', 'still-knows-it-1')
    expect(await screen.findByRole('alert')).toHaveTextContent(GENERIC)
  })

  it('LOGIN-N14 oversized input is refused before anything is sent', async () => {
    const fetchMock = mockApi({})
    renderLogin()
    await userEvent.click(email())
    await userEvent.paste(`${'x'.repeat(250)}@x.co`)
    await userEvent.click(password())
    await userEvent.paste('p'.repeat(513))
    await userEvent.click(submit())
    expect(screen.getAllByText('Use at most 254 characters')).toHaveLength(1)
    expect(screen.getByText('Use at most 512 characters')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('LOGIN-N15 only email and password are sent: no role or hospital chosen by the browser', async () => {
    const fetchMock = mockApi({ 'POST /auth/login/': ok(userFor('nurse')) })
    renderLogin()
    await signIn('nurse@hospital.test', 'valid-password-1')
    await screen.findByText('landed on /staff')
    expect(Object.keys(JSON.parse(String(posts(fetchMock)[0][1]?.body)))).toEqual(['email', 'password'])
  })
})
