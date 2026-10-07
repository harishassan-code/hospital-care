import type { Role } from '../features/staff/roles'
import { ApiError, apiGet, apiPost } from './client'

/** The signed-in account, as returned by /auth/login/, /auth/signup/ and /auth/me/. */
export interface User {
  id: number
  email: string
  fullName: string
  phone: string
  role: Role | 'patient'
  /** True for hospital staff (any role except patient). */
  isStaff: boolean
}

export type AuthErrorKind = 'invalid_credentials' | 'locked_out' | 'email_taken' | 'rejected' | 'unavailable'

export class AuthError extends Error {
  kind: AuthErrorKind

  constructor(kind: AuthErrorKind) {
    super(kind)
    this.kind = kind
  }
}

const MESSAGES: Record<AuthErrorKind, string> = {
  invalid_credentials: 'That email and password don’t match an account',
  locked_out: 'Too many failed sign-in attempts. Wait 15 minutes, or ask your hospital administrator to reset your password.',
  email_taken: 'An account with this email already exists. Log in instead.',
  rejected: 'The hospital couldn’t accept these details. Check them and try again.',
  unavailable: 'The hospital’s server didn’t respond. Try again in a moment.',
}

export function authErrorMessage(kind: AuthErrorKind): string {
  return MESSAGES[kind]
}

function statusOf(error: unknown): number {
  return error instanceof ApiError ? error.status : 0
}

export async function login(values: { email: string; password: string }): Promise<User> {
  try {
    return await apiPost<User>('/auth/login/', { email: values.email.trim(), password: values.password })
  } catch (error) {
    const status = statusOf(error)
    if (status === 429) throw new AuthError('locked_out')
    throw new AuthError(status === 400 || status === 401 ? 'invalid_credentials' : 'unavailable')
  }
}

export async function signup(values: {
  fullName: string
  email: string
  phone: string
  password: string
}): Promise<User> {
  try {
    return await apiPost<User>('/auth/signup/', {
      full_name: values.fullName.trim(),
      email: values.email.trim(),
      phone: values.phone.trim(),
      password: values.password,
    })
  } catch (error) {
    const status = statusOf(error)
    const body = error instanceof ApiError ? error.body : null
    const emailRejected = typeof body === 'object' && body !== null && 'email' in body
    if (status === 409 || (status === 400 && emailRejected)) throw new AuthError('email_taken')
    throw new AuthError(status === 400 ? 'rejected' : 'unavailable')
  }
}

/** Who is signed in, or null when nobody is. Throws AuthError('unavailable') if the server can't be reached. */
export async function getMe(): Promise<User | null> {
  try {
    return await apiGet<User>('/auth/me/')
  } catch (error) {
    const status = statusOf(error)
    if (status === 401 || status === 403) return null
    throw new AuthError('unavailable')
  }
}

export async function logout(): Promise<void> {
  await apiPost('/auth/logout/', {})
}
