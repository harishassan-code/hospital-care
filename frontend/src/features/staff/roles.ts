export type Role = 'admin' | 'doctor' | 'nurse' | 'bloodBank' | 'pharmacist'
export type Module = 'overview' | 'beds' | 'blood' | 'pharmacy'

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
]

type Access = 'view' | 'edit'

/** Who can open each module, and who can change things in it. Modules not listed are hidden. */
const ACCESS: Record<Role, Partial<Record<Module, Access>>> = {
  admin: { overview: 'view', beds: 'edit', blood: 'edit', pharmacy: 'edit' },
  doctor: { overview: 'view', beds: 'view', blood: 'view', pharmacy: 'view' },
  nurse: { overview: 'view', beds: 'edit', pharmacy: 'view' },
  bloodBank: { overview: 'view', blood: 'edit' },
  pharmacist: { overview: 'view', pharmacy: 'edit' },
}

export function canSee(role: Role, module: Module): boolean {
  return ACCESS[role][module] !== undefined
}

export function canEdit(role: Role, module: Module): boolean {
  return ACCESS[role][module] === 'edit'
}
