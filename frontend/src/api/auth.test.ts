import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthError, authErrorMessage, getMe, login, logout, signup } from './auth'

const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => {
  vi.restoreAllMocks()
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

async function kindOf(promise: Promise<unknown>) {
  try {
    await promise
  } catch (error) {
    return (error as AuthError).kind
  }
  return 'resolved'
}

describe('login', () => {
  it('posts credentials as JSON with cookies and the CSRF token, and returns the user', async () => {
    document.cookie = 'csrftoken=abc123'
    const user = { id: 3, email: 'a@b.co', fullName: 'Hina Javed', phone: '', role: 'nurse', isStaff: true }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, user))
    expect(await login({ email: 'a@b.co', password: 'pw' })).toEqual(user)
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/auth\/login\/$/)
    expect(init?.method).toBe('POST')
    expect(init?.credentials).toBe('include')
    expect(new Headers(init?.headers).get('X-CSRFToken')).toBe('abc123')
    expect(JSON.parse(String(init?.body))).toEqual({ email: 'a@b.co', password: 'pw' })
  })

  it.each([400, 401])('treats %i as wrong credentials', async (status) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(status))
    expect(await kindOf(login({ email: 'a@b.co', password: 'pw' }))).toBe('invalid_credentials')
  })

  it.each([403, 404, 500])('treats %i as the server being unavailable', async (status) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(status))
    expect(await kindOf(login({ email: 'a@b.co', password: 'pw' }))).toBe('unavailable')
  })

  it('treats a network failure as the server being unavailable', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    expect(await kindOf(login({ email: 'a@b.co', password: 'pw' }))).toBe('unavailable')
  })
})

describe('signup', () => {
  const values = { fullName: 'Sara Ahmed', email: 'a@b.co', phone: '', password: 'blood-bank-7' }

  it('sends snake_case fields to the signup endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(201))
    await signup(values)
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/auth\/signup\/$/)
    expect(JSON.parse(String(init?.body))).toEqual({
      full_name: 'Sara Ahmed',
      email: 'a@b.co',
      phone: '',
      password: 'blood-bank-7',
    })
  })

  it('treats 409 as the email being taken', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(409))
    expect(await kindOf(signup(values))).toBe('email_taken')
  })

  it('treats a 400 with an email error as the email being taken', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(400, { email: ['already exists'] }))
    expect(await kindOf(signup(values))).toBe('email_taken')
  })

  it('treats other 400s as rejected details', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(400, { password: ['too common'] }))
    expect(await kindOf(signup(values))).toBe('rejected')
  })

  it('resolves when the account is created', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(201))
    expect(await kindOf(signup(values))).toBe('resolved')
  })
})

describe('getMe', () => {
  it('returns the signed-in user', async () => {
    const user = { id: 1, email: 'a@b.co', fullName: 'A', phone: '', role: 'admin', isStaff: true }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, user))
    expect(await getMe()).toEqual(user)
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/auth\/me\/$/)
  })

  it.each([401, 403])('returns null when nobody is signed in (%i)', async (status) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(status))
    expect(await getMe()).toBeNull()
  })

  it('treats a network failure as the server being unavailable', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    expect(await kindOf(getMe())).toBe('unavailable')
  })
})

describe('logout', () => {
  it('posts to the logout endpoint and accepts an empty 204 reply', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }))
    await logout()
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/auth\/logout\/$/)
    expect(init?.method).toBe('POST')
  })
})

describe('authErrorMessage', () => {
  it('has a plain message for every kind', () => {
    expect(authErrorMessage('invalid_credentials')).toBe('That email and password don’t match an account')
    expect(authErrorMessage('email_taken')).toBe('An account with this email already exists. Log in instead.')
    expect(authErrorMessage('rejected')).toBe('The hospital couldn’t accept these details. Check them and try again.')
    expect(authErrorMessage('unavailable')).toBe('The hospital’s server didn’t respond. Try again in a moment.')
  })
})
