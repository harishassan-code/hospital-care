import { API_URL } from '../api/client'
import {
  ACCOUNT_DISABLED_MESSAGE,
  INVALID_CREDENTIALS_MESSAGE,
  LOCKOUT_THRESHOLD,
  MAX_CREDENTIAL_LENGTH,
} from './constants'
import type { AuthUser } from './roles'

export type LoginFormErrors = {
  email?: string
  password?: string
}

export type LoginResult =
  | { ok: true; user: AuthUser; token: string }
  | { ok: false; reason: 'validation'; errors: LoginFormErrors }
  | { ok: false; reason: 'invalid_credentials'; message: string }
  | { ok: false; reason: 'account_disabled'; message: string }
  | { ok: false; reason: 'locked'; message: string }

export function normalizeEmail(value: string): string {
  return value.trim().toLowerCase()
}

export function normalizeUsername(value: string): string {
  return value.trim()
}

/** Email is case-insensitive and trimmed; password is case-sensitive and not trimmed (LOGIN-N12). */
export function prepareLoginIdentifier(raw: string): { kind: 'email' | 'username'; value: string } {
  const trimmed = raw.trim()
  if (trimmed.includes('@')) {
    return { kind: 'email', value: normalizeEmail(trimmed) }
  }
  return { kind: 'username', value: normalizeUsername(trimmed) }
}

export function validateLoginForm(email: string, password: string): LoginFormErrors {
  const errors: LoginFormErrors = {}
  if (!email.trim()) errors.email = 'Email or username is required.'
  if (!password) errors.password = 'Password is required.'
  if (email.length > MAX_CREDENTIAL_LENGTH) {
    errors.email = `Must be at most ${MAX_CREDENTIAL_LENGTH} characters.`
  }
  if (password.length > MAX_CREDENTIAL_LENGTH) {
    errors.password = `Must be at most ${MAX_CREDENTIAL_LENGTH} characters.`
  }
  return errors
}

export function buildLoginRequestBody(identifier: string, password: string) {
  const { value } = prepareLoginIdentifier(identifier)
  return { email: value, password }
}

export function failedAttemptMessage(attempts: number): string | null {
  if (attempts >= LOCKOUT_THRESHOLD) {
    return 'Too many failed attempts. Try again later or contact support.'
  }
  return null
}

export async function authenticateLogin(
  identifier: string,
  password: string,
  options?: { failedAttempts?: number },
): Promise<LoginResult> {
  const fieldErrors = validateLoginForm(identifier, password)
  if (Object.keys(fieldErrors).length > 0) {
    return { ok: false, reason: 'validation', errors: fieldErrors }
  }

  const lockout = failedAttemptMessage(options?.failedAttempts ?? 0)
  if (lockout) {
    return { ok: false, reason: 'locked', message: lockout }
  }

  const body = buildLoginRequestBody(identifier, password)

  const res = await fetch(`${API_URL}/auth/login/`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (res.status === 403) {
    const data = (await res.json().catch(() => ({}))) as { code?: string }
    if (data.code === 'account_disabled') {
      return { ok: false, reason: 'account_disabled', message: ACCOUNT_DISABLED_MESSAGE }
    }
  }

  if (!res.ok) {
    return { ok: false, reason: 'invalid_credentials', message: INVALID_CREDENTIALS_MESSAGE }
  }

  const data = (await res.json()) as {
    token: string
    role: AuthUser['role']
    hospital_id: string | null
    hospital_name: string
    email: string
  }

  return {
    ok: true,
    token: data.token,
    user: {
      email: data.email,
      role: data.role,
      hospitalId: data.hospital_id,
      hospitalName: data.hospital_name,
      disabled: false,
    },
  }
}

export function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}
