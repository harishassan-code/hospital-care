export type Role = 'admin' | 'doctor' | 'nurse' | 'bloodBank' | 'pharmacist'
export type Module =
  | 'overview'
  | 'emergencies'
  | 'transfers'
  | 'beds'
  | 'blood'
  | 'pharmacy'
  | 'equipment'
  | 'operatingRooms'
  | 'orBookings'
  | 'hospitals'
  | 'users'

export const ROLES: readonly { id: Role; label: string }[] = [
  { id: 'admin', label: 'Admin' },
  { id: 'doctor', label: 'Doctor' },
  { id: 'nurse', label: 'Nurse' },
  { id: 'bloodBank', label: 'Blood bank' },
  { id: 'pharmacist', label: 'Pharmacist' },
]

export const MODULES: readonly { id: Module; label: string; path: string }[] = [
  { id: 'overview', label: 'Overview', path: '/staff' },
  { id: 'emergencies', label: 'Emergencies', path: '/staff/emergencies' },
  { id: 'transfers', label: 'Transfers', path: '/staff/transfers' },
  { id: 'beds', label: 'Beds', path: '/staff/beds' },
  { id: 'blood', label: 'Blood bank', path: '/staff/blood' },
  { id: 'pharmacy', label: 'Pharmacy', path: '/staff/pharmacy' },
  { id: 'equipment', label: 'Equipment', path: '/staff/equipment' },
  { id: 'operatingRooms', label: 'Operating rooms', path: '/staff/operating-rooms' },
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
  admin: {
    overview: 'view',
    emergencies: 'edit',
    transfers: 'edit',
    beds: 'edit',
    blood: 'edit',
    pharmacy: 'edit',
    equipment: 'edit',
    operatingRooms: 'edit',
    orBookings: 'edit',
    hospitals: 'edit',
    users: 'edit',
  },
  doctor: {
    overview: 'view',
    emergencies: 'edit',
    transfers: 'edit',
    beds: 'view',
    blood: 'view',
    pharmacy: 'view',
    equipment: 'view',
    operatingRooms: 'view',
    orBookings: 'edit', // surgeons book their own slots (story #29)
    hospitals: 'view',
  },
  nurse: {
    overview: 'view',
    emergencies: 'edit',
    transfers: 'edit',
    beds: 'edit',
    pharmacy: 'view',
    equipment: 'edit',
    operatingRooms: 'edit',
    orBookings: 'edit',
    hospitals: 'view',
  },
  bloodBank: { overview: 'view', emergencies: 'view', transfers: 'edit', blood: 'edit', hospitals: 'view' },
  pharmacist: { overview: 'view', emergencies: 'view', pharmacy: 'edit', hospitals: 'view' },
}

export function canSee(role: Role, module: Module): boolean {
  return ACCESS[role][module] !== undefined
}

export function canEdit(role: Role, module: Module): boolean {
  return ACCESS[role][module] === 'edit'
}
