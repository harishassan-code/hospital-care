import { describe, expect, it } from 'vitest'
import { canEdit, canSee, moduleForPath, MODULES, ROLES, type Module, type Role } from './roles'

// The access table from the design spec: v = view only, e = edit, - = no access.
const TABLE: Record<Role, Record<Module, 'v' | 'e' | '-'>> = {
  admin: { overview: 'v', emergencies: 'e', beds: 'e', blood: 'e', pharmacy: 'e', equipment: 'e', operatingRooms: 'e', orBookings: 'e', hospitals: 'e', users: 'e' },
  doctor: { overview: 'v', emergencies: 'e', beds: 'v', blood: 'v', pharmacy: 'v', equipment: 'v', operatingRooms: 'v', orBookings: 'e', hospitals: 'v', users: '-' },
  nurse: { overview: 'v', emergencies: 'e', beds: 'e', blood: '-', pharmacy: 'v', equipment: 'e', operatingRooms: 'e', orBookings: 'e', hospitals: 'v', users: '-' },
  bloodBank: { overview: 'v', emergencies: 'v', beds: '-', blood: 'e', pharmacy: '-', equipment: '-', operatingRooms: '-', orBookings: '-', hospitals: 'v', users: '-' },
  pharmacist: { overview: 'v', emergencies: 'v', beds: '-', blood: '-', pharmacy: 'e', equipment: '-', operatingRooms: '-', orBookings: '-', hospitals: 'v', users: '-' },
}

describe('roles', () => {
  it('lists every role and module', () => {
    expect(ROLES.map((r) => r.id)).toEqual(Object.keys(TABLE))
    expect(MODULES.map((m) => m.id)).toEqual(['overview', 'emergencies', 'beds', 'blood', 'pharmacy', 'equipment', 'operatingRooms', 'hospitals', 'users'])
  })

  it.each([
    ['/staff', 'overview'],
    ['/staff/', 'overview'],
    ['/staff/beds', 'beds'],
    ['/staff/emergencies', 'emergencies'],
    ['/staff/hospitals/3/edit', 'hospitals'],
    ['/staff/users', 'users'],
    ['/staff/equipment', 'equipment'],
    ['/staff/operating-rooms', 'operatingRooms'],
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
