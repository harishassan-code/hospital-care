import { describe, expect, it } from 'vitest'
import { canEdit, canSee, moduleForPath, MODULES, ROLES, type Module, type Role } from './roles'

// The access table from the design spec: v = view only, e = edit, - = no access.
const TABLE: Record<Role, Record<Module, 'v' | 'e' | '-'>> = {
  admin: { overview: 'v', alerts: 'v', commandCentre: 'v', emergencies: 'e', transfers: 'e', beds: 'e', blood: 'e', pharmacy: 'e', equipment: 'e', operatingRooms: 'e', orBookings: 'e', ambulances: 'e', hospitals: 'e', users: 'e', audit: 'v', donors: 'e' },
  doctor: { overview: 'v', alerts: 'v', commandCentre: '-', emergencies: 'e', transfers: 'e', beds: 'v', blood: 'v', pharmacy: 'v', equipment: 'v', operatingRooms: 'v', orBookings: 'e', ambulances: 'v', hospitals: 'v', users: '-', audit: '-', donors: '-' },
  nurse: { overview: 'v', alerts: 'v', commandCentre: '-', emergencies: 'e', transfers: 'e', beds: 'e', blood: '-', pharmacy: 'v', equipment: 'e', operatingRooms: 'e', orBookings: 'e', ambulances: 'e', hospitals: 'v', users: '-', audit: '-', donors: '-' },
  bloodBank: { overview: 'v', alerts: 'v', commandCentre: '-', emergencies: 'v', transfers: 'e', beds: '-', blood: 'e', pharmacy: '-', equipment: '-', operatingRooms: '-', orBookings: '-', ambulances: '-', hospitals: 'v', users: '-', audit: '-', donors: 'e' },
  pharmacist: { overview: 'v', alerts: 'v', commandCentre: '-', emergencies: 'v', transfers: '-', beds: '-', blood: '-', pharmacy: 'e', equipment: '-', operatingRooms: '-', orBookings: '-', ambulances: '-', hospitals: 'v', users: '-', audit: '-', donors: '-' },
}

describe('roles', () => {
  it('lists every role and module', () => {
    expect(ROLES.map((r) => r.id)).toEqual(Object.keys(TABLE))
    expect(MODULES.map((m) => m.id)).toEqual(['overview', 'alerts', 'commandCentre', 'emergencies', 'transfers', 'beds', 'blood', 'donors', 'pharmacy', 'equipment', 'operatingRooms', 'ambulances', 'hospitals', 'users', 'audit'])
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
})
