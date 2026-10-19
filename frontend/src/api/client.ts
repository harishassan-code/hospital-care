// Base URL for the Django API. Set VITE_API_URL in .env for staging/production.
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

/** A failed API call. `status` is 0 when the server couldn't be reached at all. */
export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown = null) {
    super(`API request failed with status ${status}`)
    this.status = status
    this.body = body
  }
}

function csrfToken(): string | undefined {
  return document.cookie
    .split('; ')
    .find((part) => part.startsWith('csrftoken='))
    ?.split('=')[1]
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, { credentials: 'include', ...init })
  } catch {
    throw new ApiError(0)
  }
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, body)
  return body as T
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' })
}

/** A write: sends the CSRF token Django checks on every signed-in POST, PATCH and DELETE. */
function send<T>(method: 'POST' | 'PATCH' | 'DELETE', path: string, data?: unknown): Promise<T> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const token = csrfToken()
  if (token) headers.set('X-CSRFToken', token)
  return request<T>(path, { method, headers, body: data === undefined ? undefined : JSON.stringify(data) })
}

export function apiPost<T>(path: string, data: unknown): Promise<T> {
  return send<T>('POST', path, data)
}

export function apiPatch<T>(path: string, data: unknown): Promise<T> {
  return send<T>('PATCH', path, data)
}

export function apiDelete(path: string): Promise<void> {
  return send<void>('DELETE', path)
}

/** First message per field from a DRF 400 body ({field: ["message"]}); a plain message comes back as `detail`. */
export function fieldErrors(error: unknown): Record<string, string> {
  const body = error instanceof ApiError ? error.body : null
  if (typeof body !== 'object' || body === null) return {}
  const errors: Record<string, string> = {}
  for (const [key, value] of Object.entries(body)) {
    const message = Array.isArray(value) ? value[0] : value
    if (typeof message === 'string') errors[key] = message
  }
  return errors
}
