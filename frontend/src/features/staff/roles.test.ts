import { describe, expect, it } from 'vitest'
import { canEdit, canOpen, canSee, moduleForPath, MODULES, ROLES, type Module, type Role } from './roles'

// The access table from the design spec: v = view only, e = edit, - = no access.
const TABLE: Record<Role, Record<Module, 'v' | 'e' | '-'>> = {
  admin: { overview: 'v', alerts: 'v', commandCentre: 'v', emergencies: 'e', transfers: 'e', beds: 'e', blood: 'e', pharmacy: 'e', equipment: 'e', operatingRooms: 'e', orBookings: 'e', ambulances: 'e', hospitals: 'e', specialists: 'e', users: 'e', audit: 'v', donors: 'e', reports: 'v', simulation: 'e', metrics: 'v', emergencyDepartment: 'e', staffing: 'e' },
  doctor: { overview: 'v', alerts: 'v', commandCentre: '-', emergencies: 'e', transfers: 'e', beds: 'v', blood: 'v', pharmacy: 'v', equipment: 'v', operatingRooms: 'v', orBookings: 'e', ambulances: 'v', hospitals: 'v', specialists: 'v', users: '-', audit: '-', donors: '-', reports: '-', simulation: '-', metrics: 'v', emergencyDepartment: 'e', staffing: 'v' },
  nurse: { overview: 'v', alerts: 'v', commandCentre: '-', emergencies: 'e', transfers: 'e', beds: 'e', blood: '-', pharmacy: 'v', equipment: 'e', operatingRooms: 'e', orBookings: 'e', ambulances: 'e', hospitals: 'v', specialists: 'e', users: '-', audit: '-', donors: '-', reports: '-', simulation: '-', metrics: 'v', emergencyDepartment: 'e', staffing: 'e' },
  bloodBank: { overview: 'v', alerts: 'v', commandCentre: '-', emergencies: 'v', transfers: 'e', beds: '-', blood: 'e', pharmacy: '-', equipment: '-', operatingRooms: '-', orBookings: '-', ambulances: '-', hospitals: 'v', specialists: 'v', users: '-', audit: '-', donors: 'e', reports: '-', simulation: '-', metrics: 'v', emergencyDepartment: '-', staffing: '-' },
  pharmacist: { overview: 'v', alerts: 'v', commandCentre: '-', emergencies: 'v', transfers: '-', beds: '-', blood: '-', pharmacy: 'e', equipment: '-', operatingRooms: '-', orBookings: '-', ambulances: '-', hospitals: 'v', specialists: 'v', users: '-', audit: '-', donors: '-', reports: '-', simulation: '-', metrics: 'v', emergencyDepartment: '-', staffing: '-' },
}

describe('roles', () => {
  it('lists every role and module', () => {
    expect(ROLES.map((r) => r.id)).toEqual(Object.keys(TABLE))
    expect(MODULES.map((m) => m.id)).toEqual(['overview', 'alerts', 'commandCentre', 'emergencyDepartment', 'emergencies', 'transfers', 'beds', 'blood', 'donors', 'pharmacy', 'equipment', 'operatingRooms', 'staffing', 'ambulances', 'hospitals', 'specialists', 'users', 'audit', 'reports', 'simulation'])
  })

  it.each([
    ['/staff', 'overview'],
    ['/staff/', 'overview'],
    ['/staff/alerts', 'alerts'],
    ['/staff/beds', 'beds'],
    ['/staff/emergencies', 'emergencies'],
    ['/staff/transfers', 'transfers'],
    ['/staff/transfers/3', 'transfers'],
    ['/staff/hospitals/3/edit', 'hospitals'],
    ['/staff/users', 'users'],
    ['/staff/equipment', 'equipment'],
    ['/staff/operating-rooms', 'operatingRooms'],
    ['/staff/ambulances', 'ambulances'],
    ['/staff/command-centre', 'commandCentre'],
    ['/staff/audit', 'audit'],
    ['/staff/reports', 'reports'],
    ['/staff/simulation', 'simulation'],
    ['/staff/emergency-department', 'emergencyDepartment'],
    ['/staff/staffing', 'staffing'],
    ['/staff/specialists', 'specialists'],
    ['/staff/specialists/3', 'specialists'],
    ['/staff/specialists/3/edit', 'specialists'],
    ['/staff/hospitalsx', 'overview'],
  ])('maps %s to the %s module', (path, module) => {
    expect(moduleForPath(path).id).toBe(module)
  })

  it.each(Object.entries(TABLE))('matches the access table for %s', (role, row) => {
    for (const [module, access] of Object.entries(row)) {
      expect(canSee(role as Role, module as Module), `${role} sees ${module}`).toBe(access !== '-')
      expect(canEdit(role as Role, module as Module), `${role} edits ${module}`).toBe(access === 'e')
    }
  })

  it('opens the simulation only for the CityCare admin, who has no hospital (B21)', () => {
    expect(canOpen('admin', 'simulation', false)).toBe(true)
    expect(canOpen('admin', 'simulation', true)).toBe(false)
    expect(canOpen('nurse', 'simulation', false)).toBe(false)
    expect(canOpen('admin', 'reports', true)).toBe(true)
  })

  it('opens the emergency department and staff on duty only for someone at a hospital (B22)', () => {
    expect(canOpen('nurse', 'emergencyDepartment', true)).toBe(true)
    expect(canOpen('admin', 'emergencyDepartment', false)).toBe(false)
    expect(canOpen('admin', 'staffing', false)).toBe(false)
    expect(canOpen('bloodBank', 'staffing', true)).toBe(false)
  })
})
