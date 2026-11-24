export type Role = 'admin' | 'doctor' | 'nurse' | 'bloodBank' | 'pharmacist'
export type Module =
  | 'overview'
  | 'alerts'
  | 'emergencies'
  | 'transfers'
  | 'beds'
  | 'blood'
  | 'donors'
  | 'pharmacy'
  | 'equipment'
  | 'operatingRooms'
  | 'orBookings'
  | 'ambulances'
  | 'hospitals'
  | 'specialists'
  | 'users'
  | 'commandCentre'
  | 'audit'
  | 'reports'
  | 'simulation'
  | 'metrics'
  | 'emergencyDepartment'
  | 'staffing'

export const ROLES: readonly { id: Role; label: string }[] = [
  { id: 'admin', label: 'Admin' },
  { id: 'doctor', label: 'Doctor' },
  { id: 'nurse', label: 'Nurse' },
  { id: 'bloodBank', label: 'Blood bank' },
  { id: 'pharmacist', label: 'Pharmacist' },
]

export const MODULES: readonly { id: Module; label: string; path: string }[] = [
  { id: 'overview', label: 'Overview', path: '/staff' },
  { id: 'alerts', label: 'Alerts', path: '/staff/alerts' },
  { id: 'commandCentre', label: 'City command centre', path: '/staff/command-centre' },
  { id: 'emergencyDepartment', label: 'Emergency department', path: '/staff/emergency-department' },
  { id: 'emergencies', label: 'Emergencies', path: '/staff/emergencies' },
  { id: 'transfers', label: 'Transfers', path: '/staff/transfers' },
  { id: 'beds', label: 'Beds', path: '/staff/beds' },
  { id: 'blood', label: 'Blood bank', path: '/staff/blood' },
  { id: 'donors', label: 'Donors', path: '/staff/donors' },
  { id: 'pharmacy', label: 'Pharmacy', path: '/staff/pharmacy' },
  { id: 'equipment', label: 'Equipment', path: '/staff/equipment' },
  { id: 'operatingRooms', label: 'Operating rooms', path: '/staff/operating-rooms' },
  { id: 'staffing', label: 'Staff on duty', path: '/staff/staffing' },
  { id: 'ambulances', label: 'Ambulances', path: '/staff/ambulances' },
  { id: 'hospitals', label: 'Hospitals', path: '/staff/hospitals' },
  { id: 'specialists', label: 'Specialists', path: '/staff/specialists' },
  { id: 'users', label: 'Users and roles', path: '/staff/users' },
  { id: 'audit', label: 'Audit log', path: '/staff/audit' },
  { id: 'reports', label: 'Reports', path: '/staff/reports' },
  { id: 'simulation', label: 'Simulation', path: '/staff/simulation' },
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
    alerts: 'view', // the user's own notifications; nobody edits them here
    commandCentre: 'view', // the whole network, read-only (story #55)
    emergencies: 'edit',
    transfers: 'edit',
    beds: 'edit',
    blood: 'edit',
    donors: 'edit',
    pharmacy: 'edit',
    equipment: 'edit',
    operatingRooms: 'edit',
    orBookings: 'edit',
    ambulances: 'edit',
    hospitals: 'edit',
    specialists: 'edit',
    users: 'edit',
    audit: 'view',
    reports: 'view', // operational reports and their export (B18, #66, #67); "management" is the admin
    simulation: 'edit', // the city clock and scenarios (B21): only the admin without a hospital, below
    metrics: 'view', // the hourly figures behind the trend charts (B22); no page of its own
    emergencyDepartment: 'edit', // the queue and its actions (B22)
    staffing: 'edit', // who is on duty, against the rota (B22)
  },
  doctor: {
    overview: 'view',
    alerts: 'view',
    emergencies: 'edit',
    transfers: 'edit',
    beds: 'view',
    blood: 'view',
    pharmacy: 'view',
    equipment: 'view',
    operatingRooms: 'view',
    orBookings: 'edit', // surgeons book their own slots (story #29)
    ambulances: 'view',
    hospitals: 'view',
    specialists: 'view',
    metrics: 'view',
    emergencyDepartment: 'edit',
    staffing: 'view',
  },
  nurse: {
    overview: 'view',
    alerts: 'view',
    emergencies: 'edit',
    transfers: 'edit',
    beds: 'edit',
    pharmacy: 'view',
    equipment: 'edit',
    operatingRooms: 'edit',
    orBookings: 'edit',
    ambulances: 'edit',
    hospitals: 'view',
    specialists: 'edit', // own hospital only; the API refuses other hospitals (apps.specialists.services)
    metrics: 'view',
    emergencyDepartment: 'edit',
    staffing: 'edit', // the nurse in charge covers gaps
  },
  bloodBank: { overview: 'view', alerts: 'view', emergencies: 'view', transfers: 'edit', blood: 'edit', donors: 'edit', hospitals: 'view', specialists: 'view', metrics: 'view' },
  pharmacist: { overview: 'view', alerts: 'view', emergencies: 'view', pharmacy: 'edit', hospitals: 'view', specialists: 'view', metrics: 'view' },
}

export function canSee(role: Role, module: Module): boolean {
  return ACCESS[role][module] !== undefined
}

export function canEdit(role: Role, module: Module): boolean {
  return ACCESS[role][module] === 'edit'
}

/** Modules only the CityCare admin (an admin with no hospital) uses, as IsNetworkAdmin checks on the API. */
const NETWORK_ONLY: readonly Module[] = ['simulation']
/** Modules about one hospital's own floor: someone with no hospital has none to show (the API answers 404). */
const HOSPITAL_ONLY: readonly Module[] = ['emergencyDepartment', 'staffing']

/** Whether this user sees the module: their role can, a network-only module needs no hospital, and a
 * hospital-only module needs one. */
export function canOpen(role: Role, module: Module, hasHospital: boolean): boolean {
  return deniedBecause(role, module, hasHospital) === null
}

/** Why a user can't open a module: their role, it's the CityCare admin's, or it needs a hospital. */
export function deniedBecause(role: Role, module: Module, hasHospital: boolean): 'role' | 'network' | 'hospital' | null {
  if (!canSee(role, module)) return 'role'
  if (NETWORK_ONLY.includes(module)) return hasHospital ? 'network' : null
  if (HOSPITAL_ONLY.includes(module)) return hasHospital ? null : 'hospital'
  return null
}
