import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { INVALID_CREDENTIALS_MESSAGE, MAX_CREDENTIAL_LENGTH } from '../auth/constants'
import { authenticateLogin } from '../auth/login'
import { renderWithRouter } from '../test/test-utils'
import Login from './Login'

describe('Login system — negative QA', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  afterEach(() => vi.restoreAllMocks())

  it('LOGIN-N01 shows generic invalid credentials for unknown email', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }))
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), 'unknown@hospital.com')
    await user.type(screen.getByTestId('login-password'), 'SomePass1!')
    await user.click(screen.getByTestId('login-submit'))
    expect(await screen.findByTestId('login-form-error')).toHaveTextContent(INVALID_CREDENTIALS_MESSAGE)
  })

  it('LOGIN-N02 uses the same generic error for wrong password', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }))
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), 'staff@citygeneral.org')
    await user.type(screen.getByTestId('login-password'), 'wrong-password')
    await user.click(screen.getByTestId('login-submit'))
    const message = await screen.findByTestId('login-form-error')
    expect(message).toHaveTextContent(INVALID_CREDENTIALS_MESSAGE)
    expect(message.textContent).not.toMatch(/wrong password|incorrect password/i)
  })

  it('LOGIN-N04 rejects SQL injection payloads with standard invalid-credentials handling', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }))
    const result = await authenticateLogin("' OR '1'='1", "admin'--")
    expect(result.ok).toBe(false)
    if (!result.ok && result.reason === 'invalid_credentials') {
      expect(result.message).toBe(INVALID_CREDENTIALS_MESSAGE)
    }
  })

  it('LOGIN-N05 renders XSS payload as plain text in validation errors', async () => {
    renderWithRouter(<Login />)
    fireEvent.change(screen.getByTestId('login-email'), {
      target: { value: '<script>alert(1)</script>' },
    })
    fireEvent.submit(screen.getByRole('form', { name: 'Login form' }))
    const error = await screen.findByTestId('login-password-error')
    expect(error.textContent).toBe('Password is required.')
    expect(error.innerHTML).not.toContain('<script>')
  })

  it('LOGIN-N06 blocks empty email, empty password, and both empty', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    renderWithRouter(<Login />)
    fireEvent.submit(screen.getByRole('form', { name: 'Login form' }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByTestId('login-email-error')).toBeInTheDocument()
    expect(screen.getByTestId('login-password-error')).toBeInTheDocument()

    await user.type(screen.getByTestId('login-email'), 'user@hospital.com')
    fireEvent.submit(screen.getByRole('form', { name: 'Login form' }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByTestId('login-password-error')).toBeInTheDocument()
  })

  it('LOGIN-N07 rejects deactivated accounts with a dedicated message', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ code: 'account_disabled' }), { status: 403 }),
    )
    renderWithRouter(<Login />)
    await user.type(screen.getByTestId('login-email'), 'former@citygeneral.org')
    await user.type(screen.getByTestId('login-password'), 'StillKnowsIt1!')
    await user.click(screen.getByTestId('login-submit'))
    expect(await screen.findByTestId('login-form-error')).toHaveTextContent(/disabled/i)
  })

  it('LOGIN-N11 keeps password input masked by default', () => {
    renderWithRouter(<Login />)
    expect(screen.getByTestId('login-password')).toHaveAttribute('type', 'password')
  })

  it('LOGIN-N14 rejects oversized credential input before calling the API', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    renderWithRouter(<Login />)
    const long = 'x'.repeat(MAX_CREDENTIAL_LENGTH + 1)
    fireEvent.change(screen.getByTestId('login-email'), { target: { value: long } })
    fireEvent.change(screen.getByTestId('login-password'), { target: { value: 'short' } })
    fireEvent.submit(screen.getByRole('form', { name: 'Login form' }))
    await waitFor(() => expect(screen.getByTestId('login-email-error')).toBeInTheDocument())
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
