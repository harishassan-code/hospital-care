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

/** Roles that work at one hospital: the API refuses them without one (400 {hospitalId: [...]}). */
export const HOSPITAL_ROLES: readonly AccountRole[] = ['doctor', 'nurse', 'bloodBank', 'pharmacist']

/**
 * PATCH /api/users/<id>/ (users: edit). 400 {role: [...]} or {hospitalId: [...]} when refused.
 * `hospitalId` is sent only when it changes: left out keeps the user's hospital, null clears it.
 */
export function updateUserRole(id: number, role: AccountRole, hospitalId?: number | null): Promise<UserSummary> {
  return apiPatch<UserSummary>(`/users/${id}/`, hospitalId === undefined ? { role } : { role, hospitalId })
}
