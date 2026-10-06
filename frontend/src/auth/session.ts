import type { AuthUser } from './roles'

const SESSION_KEY = 'carelink.session'
const REMEMBER_KEY = 'carelink.remember'

export type StoredSession = {
  token: string
  user: AuthUser
}

export function saveSession(session: StoredSession, remember: boolean): void {
  const payload = JSON.stringify(session)
  if (remember) {
    localStorage.setItem(REMEMBER_KEY, payload)
    sessionStorage.removeItem(SESSION_KEY)
  } else {
    sessionStorage.setItem(SESSION_KEY, payload)
    localStorage.removeItem(REMEMBER_KEY)
  }
}

export function loadSession(): StoredSession | null {
  const raw = sessionStorage.getItem(SESSION_KEY) ?? localStorage.getItem(REMEMBER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as StoredSession
  } catch {
    return null
  }
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY)
  localStorage.removeItem(REMEMBER_KEY)
}

export function getAuthHeaders(session: StoredSession | null): HeadersInit {
  if (!session) return {}
  return { Authorization: `Bearer ${session.token}` }
}
