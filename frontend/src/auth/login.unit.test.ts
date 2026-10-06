import { describe, expect, it } from 'vitest'
import { INVALID_CREDENTIALS_MESSAGE, MAX_CREDENTIAL_LENGTH } from './constants'
import {
  buildLoginRequestBody,
  escapeHtml,
  failedAttemptMessage,
  normalizeEmail,
  prepareLoginIdentifier,
  validateLoginForm,
} from './login'

describe('LOGIN-N12 case sensitivity and whitespace', () => {
  it('normalizes email case and trims surrounding spaces', () => {
    expect(prepareLoginIdentifier('  User@Hospital.COM  ')).toEqual({
      kind: 'email',
      value: 'user@hospital.com',
    })
  })

  it('does not trim password (handled by caller — password sent as typed)', () => {
    expect(buildLoginRequestBody('user@hospital.com', ' secret ').password).toBe(' secret ')
  })
})

describe('LOGIN-N14 oversized input', () => {
  it('flags email and password longer than the maximum', () => {
    const long = 'a'.repeat(MAX_CREDENTIAL_LENGTH + 1)
    const errors = validateLoginForm(long, long)
    expect(errors.email).toMatch(/at most/)
    expect(errors.password).toMatch(/at most/)
  })
})

describe('LOGIN-N15 login request body', () => {
  it('sends only email and password — no client-supplied role or hospital', () => {
    const body = buildLoginRequestBody('staff@citygeneral.org', 'P@ssw0rd!')
    expect(body).toEqual({ email: 'staff@citygeneral.org', password: 'P@ssw0rd!' })
    expect(Object.keys(body)).toEqual(['email', 'password'])
  })
})

describe('LOGIN-N03 lockout threshold', () => {
  it('returns a lockout message at the configured threshold', () => {
    expect(failedAttemptMessage(4)).toBeNull()
    expect(failedAttemptMessage(5)).toMatch(/Too many failed attempts/)
  })
})

describe('LOGIN-N05 XSS escaping helper', () => {
  it('escapes script tags for safe rendering', () => {
    expect(escapeHtml('<script>alert(1)</script>')).toBe(
      '&lt;script&gt;alert(1)&lt;/script&gt;',
    )
  })
})

describe('LOGIN-N01/N02 shared invalid-credentials copy', () => {
  it('uses one generic message constant for failed auth', () => {
    expect(INVALID_CREDENTIALS_MESSAGE).toMatch(/Invalid credentials/i)
    expect(INVALID_CREDENTIALS_MESSAGE).not.toMatch(/email.*exist/i)
  })
})

describe('normalizeEmail', () => {
  it('lowercases valid emails', () => {
    expect(normalizeEmail('Admin@CityCare.org')).toBe('admin@citycare.org')
  })
})
