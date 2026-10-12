import { vi } from 'vitest'
import type { User } from '../api/auth'
import type { BedAction, BedBoard } from '../api/beds'
import type { HospitalInput, StructureKind } from '../api/hospitals'
import type { PublicStatus } from '../api/publicStatus'
import type { UserSummary } from '../api/users'
import { applyAction } from '../features/beds/beds'
import { canEdit, canSee, type Module, type Role } from '../features/staff/roles'
import { sampleBedBoard } from './fixtures/beds'
import { sampleBloodUnits } from './fixtures/blood'
import { sampleCapabilities, sampleHospitals, sampleUsers } from './fixtures/hospitals'
import { sampleMedicines } from './fixtures/pharmacy'
import { samplePublicStatus } from './fixtures/publicStatus'

export type Reply = { status?: number; body?: unknown }
type Request = { params: Record<string, string>; body: unknown }
type Route = Reply | ((request: Request) => Reply)

export const ok = (body?: unknown): Reply => ({ status: 200, body })
export const fail = (status: number, body: unknown = { detail: 'Request failed' }): Reply => ({ status, body })

/** "/beds/:id/actions/" against "/beds/ICU-01/actions/" → { id: "ICU-01" }, or null when it doesn't match. */
function match(pattern: string, path: string): Record<string, string> | null {
  const want = pattern.split('/')
  const got = path.split('/')
  if (want.length !== got.length) return null
  const params: Record<string, string> = {}
  for (let i = 0; i < want.length; i++) {
    if (want[i].startsWith(':')) params[want[i].slice(1)] = decodeURIComponent(got[i])
    else if (want[i] !== got[i]) return null
  }
  return params
}

/**
 * Replace fetch with a fake API. Keys are "METHOD /path/" relative to /api, with :params.
 * Unknown routes answer 404, like the real server.
 */
export function mockApi(routes: Record<string, Route>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input)).pathname.replace(/^\/api/, '')
    const method = (init?.method ?? 'GET').toUpperCase()
    for (const [key, route] of Object.entries(routes)) {
      const [routeMethod, pattern] = key.split(' ')
      const params = routeMethod === method ? match(pattern, path) : null
      if (!params) continue
      const body = init?.body ? JSON.parse(String(init.body)) : undefined
      const reply = typeof route === 'function' ? route({ params, body }) : route
      const status = reply.status ?? 200
      return new Response(status === 204 ? null : JSON.stringify(reply.body ?? {}), { status })
    }
    return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
  })
}

/** What the server fills in for a new structure item. */
const STRUCTURE_DEFAULTS: Record<StructureKind, Record<string, unknown>> = {
  departments: {},
  wards: { code: 'new-ward', kind: '', departmentId: null, bedCount: 0 },
  locations: {},
}

const NAMES: Record<Role | 'patient', string> = {
  admin: 'Sadia Admin',
  doctor: 'Dr. Ayesha Khan',
  nurse: 'Hina Javed',
  bloodBank: 'Kashif Mehmood',
  pharmacist: 'Rabia Anwar',
  patient: 'Sara Ahmed',
}

export function userFor(role: Role | 'patient'): User {
  const hospital = role === 'patient' ? null : { id: 1, name: 'CityCare General Hospital' }
  return { id: 1, email: `${role.toLowerCase()}@demo.test`, fullName: NAMES[role], phone: '', role, isStaff: role !== 'patient', hospital }
}

/**
 * The staff API as the backend behaves: /auth/me/ for the given role (or 403 when signed out),
 * modules gated by the same access table, and bed actions that change the board or answer 409.
 */
type StaffApiOptions = {
  role: Role | 'patient' | null
  /** Make GET /public/status/ fail. */
  erDown?: boolean
  /** Use this board instead of the sample one. */
  board?: BedBoard
  /** Use this public status instead of the sample one. */
  publicStatus?: PublicStatus
  /** Make every hospitals and users call fail as if the server were down. */
  networkDown?: boolean
}

export function mockStaffApi({ role, erDown = false, board: customBoard, publicStatus, networkDown = false }: StaffApiOptions) {
  const now = new Date()
  const board = customBoard ?? sampleBedBoard(now)
  const hospitals = sampleHospitals()
  const users = sampleUsers()
  const gate = (module: Module, reply: () => Reply): Route => () =>
    role && role !== 'patient' && canSee(role, module) ? reply() : fail(403)
  /** Like gate, but the reply sees the request, and `networkDown` fails it. Reads need view, writes need edit. */
  const allowed =
    (check: typeof canSee) =>
    (module: Module, reply: (request: Request) => Reply): Route =>
    (request) => {
      if (networkDown) return fail(503)
      return role && role !== 'patient' && check(role, module) ? reply(request) : fail(403)
    }
  const view = allowed(canSee)
  const edit = allowed(canEdit)
  const findHospital = (id: string) => hospitals.find((h) => h.id === Number(id))
  let nextId = 100

  const fetchMock = mockApi({
    'GET /auth/me/': role ? ok(userFor(role)) : fail(403),
    'POST /auth/logout/': { status: 204 },
    'GET /public/status/': erDown ? fail(503) : ok(publicStatus ?? samplePublicStatus(now)),
    'GET /beds/': gate('beds', () => ok(board)),
    'GET /blood/units/': gate('blood', () => ok(sampleBloodUnits(now))),
    'GET /pharmacy/stock/': gate('pharmacy', () => ok(sampleMedicines(now))),
    'POST /beds/:id/actions/': ({ params, body }) => {
      if (!role || role === 'patient' || !canEdit(role, 'beds')) return fail(403)
      const index = board.beds.findIndex((b) => b.id === params.id)
      if (index < 0) return fail(404)
      try {
        board.beds[index] = applyAction(board.beds[index], (body as { action: BedAction }).action, new Date())
      } catch (error) {
        return fail(409, { detail: (error as Error).message })
      }
      return ok(board.beds[index])
    },

    'GET /users/': view('users', () => ok(users)),
    'PATCH /users/:id/': edit('users', ({ params, body }) => {
      const user = users.find((u) => u.id === Number(params.id))
      if (!user) return fail(404)
      if (user.roleLocked) return fail(400, { role: ['You can’t change your own role.'] })
      user.role = (body as { role: UserSummary['role'] }).role
      return ok(user)
    }),

    // Before /hospitals/:id/, which would otherwise match it.
    'GET /hospitals/capabilities/': view('hospitals', () => ok(sampleCapabilities)),
    'GET /hospitals/': view('hospitals', () => ok(hospitals)),
    'POST /hospitals/': edit('hospitals', ({ body }) => {
      const input = body as HospitalInput
      if (hospitals.some((h) => h.name.toLowerCase() === input.name.toLowerCase())) {
        return fail(400, { name: ['A hospital with this name is already registered.'] })
      }
      const created = { ...input, id: nextId++, departments: [], wards: [], locations: [] }
      hospitals.push(created)
      return { status: 201, body: created }
    }),
    'GET /hospitals/:id/': view('hospitals', ({ params }) => {
      const hospital = findHospital(params.id)
      return hospital ? ok(hospital) : fail(404)
    }),
    'PATCH /hospitals/:id/': edit('hospitals', ({ params, body }) => {
      const hospital = findHospital(params.id)
      if (!hospital) return fail(404)
      Object.assign(hospital, body)
      return ok(hospital)
    }),
    'POST /hospitals/:id/:kind/': edit('hospitals', ({ params, body }) => {
      const hospital = findHospital(params.id)
      const kind = params.kind as StructureKind
      if (!hospital || !(kind in STRUCTURE_DEFAULTS)) return fail(404)
      const data = body as { name: string }
      const list = hospital[kind] as { id: number; name: string }[]
      if (list.some((item) => item.name.toLowerCase() === data.name.toLowerCase())) {
        return fail(400, { name: ['This hospital already has one with that name.'] })
      }
      const item = { ...STRUCTURE_DEFAULTS[kind], ...data, id: nextId++ }
      list.push(item)
      return { status: 201, body: item }
    }),
    'DELETE /hospitals/:id/:kind/:item/': edit('hospitals', ({ params }) => {
      const hospital = findHospital(params.id)
      const kind = params.kind as StructureKind
      if (!hospital || !(kind in STRUCTURE_DEFAULTS)) return fail(404)
      const list = hospital[kind] as { id: number; bedCount?: number }[]
      const index = list.findIndex((item) => item.id === Number(params.item))
      if (index < 0) return fail(404)
      if (list[index].bedCount) return fail(409, { detail: 'This ward still has beds. Move or remove them first.' })
      list.splice(index, 1)
      return { status: 204 }
    }),
  })
  return { fetchMock, board, hospitals, users }
}
