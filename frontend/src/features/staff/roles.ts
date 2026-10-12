export type Role = 'admin' | 'doctor' | 'nurse' | 'bloodBank' | 'pharmacist'
export type Module = 'overview' | 'beds' | 'blood' | 'pharmacy' | 'hospitals' | 'users'

export const ROLES: readonly { id: Role; label: string }[] = [
  { id: 'admin', label: 'Admin' },
  { id: 'doctor', label: 'Doctor' },
  { id: 'nurse', label: 'Nurse' },
  { id: 'bloodBank', label: 'Blood bank' },
  { id: 'pharmacist', label: 'Pharmacist' },
]

export const MODULES: readonly { id: Module; label: string; path: string }[] = [
  { id: 'overview', label: 'Overview', path: '/staff' },
  { id: 'beds', label: 'Beds', path: '/staff/beds' },
  { id: 'blood', label: 'Blood bank', path: '/staff/blood' },
  { id: 'pharmacy', label: 'Pharmacy', path: '/staff/pharmacy' },
  { id: 'hospitals', label: 'Hospitals', path: '/staff/hospitals' },
  { id: 'users', label: 'Users and roles', path: '/staff/users' },
]

/** The module a staff path belongs to, e.g. /staff/hospitals/3/edit → hospitals. Anything else → overview. */
export function moduleForPath(pathname: string): (typeof MODULES)[number] {
  const path = pathname.replace(/\/$/, '')
  return MODULES.find((m) => m.id !== 'overview' && (path === m.path || path.startsWith(`${m.path}/`))) ?? MODULES[0]
}

type Access = 'view' | 'edit'

/**
 * Who can open each module, and who can change things in it. Modules not listed are hidden.
 * Keep identical to ACCESS in backend/apps/accounts/permissions.py: the API enforces it, this only hides things.
 */
const ACCESS: Record<Role, Partial<Record<Module, Access>>> = {
  admin: { overview: 'view', beds: 'edit', blood: 'edit', pharmacy: 'edit', hospitals: 'edit', users: 'edit' },
  doctor: { overview: 'view', beds: 'view', blood: 'view', pharmacy: 'view', hospitals: 'view' },
  nurse: { overview: 'view', beds: 'edit', pharmacy: 'view', hospitals: 'view' },
  bloodBank: { overview: 'view', blood: 'edit', hospitals: 'view' },
  pharmacist: { overview: 'view', pharmacy: 'edit', hospitals: 'view' },
}

export function canSee(role: Role, module: Module): boolean {
  return ACCESS[role][module] !== undefined
}

export function canEdit(role: Role, module: Module): boolean {
  return ACCESS[role][module] === 'edit'
}
