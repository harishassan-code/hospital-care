import type { AuthUser } from '../auth/roles'

export function mockLoginResponse(user: AuthUser, token = 'test-token') {
  return new Response(
    JSON.stringify({
      token,
      email: user.email,
      role: user.role,
      hospital_id: user.hospitalId,
      hospital_name: user.hospitalName,
    }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  )
}

export const staffUser: AuthUser = {
  email: 'staff@citygeneral.org',
  role: 'hospital_staff',
  hospitalId: 'hosp-city-general',
  hospitalName: 'City General',
}

export const adminUser: AuthUser = {
  email: 'admin@citycare.org',
  role: 'admin',
  hospitalId: null,
  hospitalName: 'CityCare',
}

export const coordinatorUser: AuthUser = {
  email: 'coord@citygeneral.org',
  role: 'coordinator',
  hospitalId: 'hosp-city-general',
  hospitalName: 'City General',
}
