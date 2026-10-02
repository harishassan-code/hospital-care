// Base URL for the Django API. Set VITE_API_URL in .env for staging/production.
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { credentials: 'include' })
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json() as Promise<T>
}
