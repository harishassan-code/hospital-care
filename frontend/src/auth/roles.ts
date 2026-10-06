export type UserRole = 'admin' | 'hospital_staff' | 'coordinator'

export type AuthUser = {
  email: string
  role: UserRole
  hospitalId: string | null
  hospitalName: string
  disabled?: boolean
}

export function getPostLoginPath(user: AuthUser, returnTo?: string | null): string {
  if (returnTo && returnTo.startsWith('/') && !returnTo.startsWith('//')) {
    return returnTo
  }
  switch (user.role) {
    case 'admin':
      return '/admin'
    case 'coordinator':
      return '/emergency/new'
    default:
      return '/dashboard'
  }
}
