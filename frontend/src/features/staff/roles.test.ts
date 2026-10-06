import { describe, expect, it } from 'vitest'
import { canEdit, canSee, MODULES, ROLES, type Module, type Role } from './roles'

// The access table from the design spec: v = view only, e = edit, - = no access.
const TABLE: Record<Role, Record<Module, 'v' | 'e' | '-'>> = {
  admin: { overview: 'v', beds: 'e', blood: 'e', pharmacy: 'e' },
  doctor: { overview: 'v', beds: 'v', blood: 'v', pharmacy: 'v' },
  nurse: { overview: 'v', beds: 'e', blood: '-', pharmacy: 'v' },
  bloodBank: { overview: 'v', beds: '-', blood: 'e', pharmacy: '-' },
  pharmacist: { overview: 'v', beds: '-', blood: '-', pharmacy: 'e' },
}

describe('roles', () => {
  it('lists every role and module', () => {
    expect(ROLES.map((r) => r.id)).toEqual(Object.keys(TABLE))
    expect(MODULES.map((m) => m.id)).toEqual(['overview', 'beds', 'blood', 'pharmacy'])
  })

  it.each(Object.entries(TABLE))('matches the access table for %s', (role, row) => {
    for (const [module, access] of Object.entries(row)) {
      expect(canSee(role as Role, module as Module), `${role} sees ${module}`).toBe(access !== '-')
      expect(canEdit(role as Role, module as Module), `${role} edits ${module}`).toBe(access === 'e')
    }
  })
})
