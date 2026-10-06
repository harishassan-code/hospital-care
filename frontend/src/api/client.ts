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

export function apiPost<T>(path: string, data: unknown): Promise<T> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const token = csrfToken()
  if (token) headers.set('X-CSRFToken', token)
  return request<T>(path, { method: 'POST', headers, body: JSON.stringify(data) })
}
