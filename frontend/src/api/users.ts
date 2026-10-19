import type { User } from './auth'
import { apiGet, apiPatch } from './client'

export type AccountRole = User['role']

/** One row of the admin's user list. GET /api/users/ (users: view). */
export interface UserSummary {
  id: number
  email: string
  fullName: string
  role: AccountRole
  hospital: User['hospital']
  isActive: boolean
  /** Your own account and superusers: the role can't be changed here. */
  roleLocked: boolean
}

export function getUsers(): Promise<UserSummary[]> {
  return apiGet<UserSummary[]>('/users/')
}

/** PATCH /api/users/<id>/ (users: edit). 400 {role: [...]} when refused. */
export function updateUserRole(id: number, role: AccountRole): Promise<UserSummary> {
  return apiPatch<UserSummary>(`/users/${id}/`, { role })
}
