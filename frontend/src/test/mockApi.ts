import { vi } from 'vitest'
import type { User } from '../api/auth'
import type { BedAction, BedBoard } from '../api/beds'
import type {
  CandidatesResponse,
  CaseAction,
  CaseAllocation,
  CaseInput,
  CaseReservation,
  CaseStatus,
  Need,
  EmergencyCase,
  EmergencyCaseDetail,
  FeedEntry,
  HeldReservation,
  ResourceType,
  Severity,
  StatusChange,
} from '../api/emergencies'
import { COMPONENTS, REQUIRED_TESTS, type BloodUnit, type BloodUnitInput, type ScreeningTest, type TestResult } from '../api/blood'
import type { Equipment, EquipmentAction, EquipmentInput } from '../api/equipment'
import type {
  OperatingRoom,
  OperatingRoomAction,
  OperatingRoomInput,
  OrBooking,
  OrBookingInput,
  OrCapability,
} from '../api/operatingRooms'
import type { HospitalInput, StructureKind } from '../api/hospitals'
import type { PublicStatus } from '../api/publicStatus'
import type { UserSummary } from '../api/users'
import { applyAction } from '../features/beds/beds'
import { actionsFor, nextStatus, STATUS_LABEL } from '../features/emergencies/emergencies'
import { applyEquipmentAction } from '../features/equipment/equipment'
import { applyOperatingRoomAction } from '../features/operatingRooms/operatingRooms'
import { canEdit, canSee, type Module, type Role } from '../features/staff/roles'
import { dateKey } from '../lib/time'
import { sampleBedBoard } from './fixtures/beds'
import { sampleBloodUnits } from './fixtures/blood'
import { sampleCandidates, sampleCases, sampleLocalAvailable, sampleNetworkRequests } from './fixtures/emergencies'
import { sampleCapabilities, sampleHospitals, sampleUsers } from './fixtures/hospitals'
import { sampleMedicines } from './fixtures/pharmacy'
import { samplePublicStatus } from './fixtures/publicStatus'

export type Reply = { status?: number; body?: unknown }
type Request = { params: Record<string, string>; body: unknown; query: URLSearchParams }
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
    const url = new URL(String(input))
    const path = url.pathname.replace(/^\/api/, '')
    const method = (init?.method ?? 'GET').toUpperCase()
    for (const [key, route] of Object.entries(routes)) {
      const [routeMethod, pattern] = key.split(' ')
      const params = routeMethod === method ? match(pattern, path) : null
      if (!params) continue
      const body = init?.body ? JSON.parse(String(init.body)) : undefined
      const reply = typeof route === 'function' ? route({ params, body, query: url.searchParams }) : route
      const status = reply.status ?? 200
      return new Response(status === 204 ? null : JSON.stringify(reply.body ?? {}), { status })
    }
    return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
  })
}

/** The module whose edit right lets a role allocate each type (story #45), as in the server's ALLOCATION_MODULE. */
const TYPE_MODULE: Record<ResourceType, Module> = { blood: 'blood', bed: 'beds', equipment: 'equipment', operatingRoom: 'operatingRooms' }

/** The case statuses that still take stock (the server's RESERVABLE). */
const RESERVABLE_STATUSES: readonly CaseStatus[] = ['open', 'matching', 'partiallyFulfilled', 'escalated']

const SEVERITY_RANK: Record<Severity, number> = { critical: 0, high: 1, moderate: 2, low: 3 }

/** The order the server lists cases in: most severe first, then the oldest case first (story #31). */
const byPriority = (a: Pick<EmergencyCase, 'severity' | 'createdAt'>, b: Pick<EmergencyCase, 'severity' | 'createdAt'>) =>
  SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || a.createdAt.localeCompare(b.createdAt)

/** The statuses the network feed lists (story #36). */
const FEED_STATUSES: readonly CaseStatus[] = ['open', 'matching', 'partiallyFulfilled', 'escalated']

/** A case as the network feed lists it: the same request, with nothing filled yet. */
const feedEntryOf = (c: EmergencyCase): FeedEntry => ({
  reference: c.id,
  hospital: c.hospital,
  severity: c.severity,
  status: c.status,
  createdAt: c.createdAt,
  needs: c.items.map((need) => ({ ...need, fulfilled: 0 })),
})

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
  /** Make every hospitals, users and emergencies call fail as if the server were down. */
  networkDown?: boolean
  /** Use these emergency cases instead of the sample ones. */
  cases?: EmergencyCase[]
  /** Replace a case's timeline (by reference), e.g. to show an entry the system made. */
  histories?: Record<string, StatusChange[]>
  /** Use this network feed instead of the sample one, which is these cases plus another hospital's requests. */
  feed?: FeedEntry[]
  /** Use these sources (story #38) for whichever case is asked for, instead of the sample ones. */
  candidates?: CandidatesResponse
  /** Free units per need (in item order) by case, instead of the sample stock. */
  stock?: Record<string, number[]>
  /** Start with this many units held for a case's need, as if reserved earlier (story #43). */
  held?: { reference: string; itemId: number; count: number }[]
}

/** A few pieces of equipment across types and statuses (story #26). */
export function sampleEquipment(now: Date): Equipment[] {
  const at = now.toISOString()
  const item = (id: number, identifier: string, type: Equipment['type'], status: Equipment['status'], location: string) =>
    ({ id, identifier, type, status, location, name: '', statusSince: at, hospital: 'CityCare General Hospital' }) satisfies Equipment
  return [
    item(1, 'VENT-001', 'ventilator', 'inUse', 'ICU bay 1'),
    item(2, 'VENT-002', 'ventilator', 'available', 'ICU bay 2'),
    item(3, 'VENT-003', 'ventilator', 'maintenance', 'HDU'),
    item(4, 'DEFIB-001', 'defibrillator', 'available', 'Emergency department'),
    item(5, 'DIAL-001', 'dialysis', 'outOfService', 'Dialysis unit'),
  ]
}

/** A few operating rooms across capabilities and statuses, sorted by name as the server returns them (story #28). */
export function sampleOperatingRooms(now: Date): OperatingRoom[] {
  const at = now.toISOString()
  const room = (id: number, name: string, capabilities: OrCapability[], status: OperatingRoom['status'], location: string) =>
    ({ id, name, capabilities, status, location, statusSince: at, hospital: 'CityCare General Hospital' }) satisfies OperatingRoom
  return [
    room(1, 'Cardiac theatre', ['cardiac', 'general'], 'inUse', 'Block B, floor 3'),
    room(2, 'OR 1', ['general'], 'available', 'Block B, floor 2'),
    room(3, 'Trauma theatre', ['general', 'neuro', 'trauma'], 'cleaning', 'Emergency block, floor 1'),
  ]
}

/** Today's bookings (story #29): two in OR 1 with a gap before the next, one in Cardiac theatre. Times in Karachi. */
export function sampleOrBookings(now: Date): OrBooking[] {
  const day = dateKey(now)
  const slot = (id: number, roomId: number, start: string, end: string, procedure: string, surgeon: string): OrBooking => ({
    id,
    roomId,
    startsAt: `${day}T${start}:00+05:00`,
    endsAt: `${day}T${end}:00+05:00`,
    procedure,
    surgeon,
    patientInitials: 'A.K.',
    status: 'booked',
    bookedBy: 'Hina Javed',
    canCancel: true,
  })
  return [
    slot(1, 1, '09:00', '13:00', 'CABG', 'Dr. Ayesha Khan'),
    slot(2, 2, '08:00', '10:00', 'Appendicectomy', 'Dr. Bilal Ahmed'),
    slot(3, 2, '10:00', '12:30', 'Cholecystectomy', 'Dr. Bilal Ahmed'),
  ]
}

/** A resource's name as staff see it on a hold: "O- red cells DN-0001", "Bed ICU-01", "Ventilator VENT-001", "OR 1". */
function resourceLabel(need: Need, id: number): string {
  if (need.type === 'blood') return `${need.group} ${need.component === 'redCells' ? 'red cells' : need.component} DN-${String(id).padStart(4, '0')}`
  if (need.type === 'bed') return `Bed ${need.bedType.toUpperCase()}-${String(id).padStart(2, '0')}`
  if (need.type === 'equipment') return `${need.equipmentType === 'ventilator' ? 'Ventilator' : need.equipmentType} VENT-${String(id).padStart(3, '0')}`
  return `OR ${id}`
}

/** A need as the server labels it on a held reservation: "O- red cells", "ICU bed", "Ventilator", "Cardiac operating room". */
function needLabel(need: Need): string {
  if (need.type === 'blood') return `${need.group} ${need.component === 'redCells' ? 'red cells' : need.component}`
  if (need.type === 'bed') return `${need.bedType.toUpperCase()} bed`
  if (need.type === 'equipment') return need.equipmentType === 'ventilator' ? 'Ventilator' : need.equipmentType
  return `${need.capability} operating room`
}

/** "+05:00"-stamped time as HH:MM, the way the server words a clash. */
const clock = (iso: string) => iso.slice(11, 16)

export function mockStaffApi({
  role,
  erDown = false,
  board: customBoard,
  publicStatus,
  networkDown = false,
  cases: customCases,
  histories: customHistories,
  feed: customFeed,
  candidates: customCandidates,
  stock: customStock,
  held: seedHolds = [],
}: StaffApiOptions) {
  const now = new Date()
  const board = customBoard ?? sampleBedBoard(now)
  const units = sampleBloodUnits(now)
  const hospitals = sampleHospitals()
  const users = sampleUsers()
  const cases = customCases ?? sampleCases(now)
  /** Each case's timeline, as the server keeps it. A case that starts here has only its opening entry. */
  const openingEntry = (c: EmergencyCase): StatusChange => ({
    fromStatus: '',
    toStatus: 'open',
    action: 'create',
    note: '',
    actor: c.createdBy || null,
    at: c.createdAt,
  })
  const histories = new Map<string, StatusChange[]>(cases.map((c) => [c.id, [openingEntry(c)]]))
  for (const [reference, entries] of Object.entries(customHistories ?? {})) histories.set(reference, entries)
  const findCase = (reference: string) => cases.find((c) => c.id === reference)
  /** Free units per need at this hospital, from the sample stock. A hold takes one unit; a release gives it back. */
  const localStock = new Map<string, number[]>()
  const stockOf = (c: EmergencyCase): number[] => {
    if (!localStock.has(c.id)) localStock.set(c.id, c.items.map((_, i) => (customStock ?? sampleLocalAvailable)[c.id]?.[i] ?? 0))
    return localStock.get(c.id)!
  }
  /** Each case's holds on its stock, held or ended (story #43). Each hold is one unit of one need. */
  const holdsByCase = new Map<string, CaseReservation[]>()
  const holdsOf = (reference: string): CaseReservation[] => {
    if (!holdsByCase.has(reference)) holdsByCase.set(reference, [])
    return holdsByCase.get(reference)!
  }
  let nextHoldId = 1
  /** What each case's needs have had allocated (story #45), in item order, and the allocations made. */
  const fulfilledByCase = new Map<string, number[]>()
  const fulfilledFor = (reference: string, itemId: number) => fulfilledByCase.get(reference)?.[itemId - 1] ?? 0
  const allocationsByCase = new Map<string, CaseAllocation[]>()
  /** Whether the signed-in role may allocate this hold: it is held, and the role can edit its type's module. */
  const canAllocateHold = (c: EmergencyCase, hold: CaseReservation) =>
    hold.status === 'held' && !!role && role !== 'patient' && canEdit(role, TYPE_MODULE[c.items[hold.itemId - 1]!.type])
  const heldFor = (reference: string, itemId: number) =>
    holdsOf(reference).filter((hold) => hold.itemId === itemId && hold.status === 'held').length
  /** The case as the server returns it: each need with what this hospital has (story #33) and its holds (story #43). */
  const detailOf = (c: EmergencyCase): EmergencyCaseDetail => {
    const local = stockOf(c)
    const items = c.items.map((need, i) => {
      const reserved = heldFor(c.id, i + 1)
      const available = local[i] ?? 0
      const fulfilled = fulfilledFor(c.id, i + 1)
      return {
        ...need,
        itemId: i + 1,
        fulfilled,
        remaining: need.quantity - fulfilled,
        localAvailable: available,
        shortfall: Math.max(0, need.quantity - fulfilled - reserved - available),
        reserved,
      }
    })
    const history = histories.get(c.id) ?? []
    const closes = history.filter((change) => change.action === 'close')
    return {
      ...c,
      items,
      shortfallTotal: items.reduce((sum, need) => sum + need.shortfall, 0),
      history,
      actions: actionsFor(c.status),
      outcome: closes.length ? closes[closes.length - 1].note : null,
      reservations: holdsOf(c.id)
        .filter((hold) => hold.status === 'held' || hold.status === 'allocated')
        .map((hold) => ({ ...hold, canAllocate: canAllocateHold(c, hold) })),
      allocations: allocationsByCase.get(c.id) ?? [],
    }
  }
  /** Hold up to `quantity` free units for a need (story #43). Each hold is one unit; a case that is open starts matching. */
  const makeHolds = (found: EmergencyCase, itemId: number, quantity: number): CaseReservation[] => {
    const need = found.items[itemId - 1]!
    const stock = stockOf(found)
    const taken = Math.min(stock[itemId - 1] ?? 0, quantity)
    stock[itemId - 1] -= taken
    const hospital = found.hospital ?? { id: 0, name: '' }
    const made: CaseReservation[] = Array.from({ length: taken }, () => {
      const id = nextHoldId++
      return {
        id,
        itemId,
        resource: resourceLabel(need, id),
        hospital,
        status: 'held',
        expiresAt: new Date(Date.now() + 30 * 60_000).toISOString(),
        reservedBy: role ? NAMES[role] : '',
        canAllocate: false,
      }
    })
    holdsOf(found.id).push(...made)
    if (taken > 0 && found.status === 'open') {
      histories.set(found.id, [
        ...(histories.get(found.id) ?? []),
        { fromStatus: 'open', toStatus: 'matching', action: 'startMatching', note: `Stock reserved at ${hospital.name}`, actor: null, at: new Date().toISOString() },
      ])
      found.status = 'matching'
    }
    return made
  }
  for (const { reference, itemId, count } of seedHolds) makeHolds(findCase(reference)!, itemId, count)
  const findHold = (id: number) => {
    for (const c of cases) {
      const hold = holdsOf(c.id).find((h) => h.id === id)
      if (hold) return { c, hold }
    }
    return undefined
  }
  /** Why this hold can't be allocated now, as the server answers it, or null when it can (stories #45, #46). */
  const allocationRefusal = (c: EmergencyCase, hold: CaseReservation): Reply | null => {
    if (!role || role === 'patient' || !canEdit(role, TYPE_MODULE[c.items[hold.itemId - 1]!.type])) {
      return fail(403, { detail: 'Your role can’t allocate this.' })
    }
    if (hold.status !== 'held') {
      return fail(409, {
        detail: hold.status === 'allocated' ? 'This reservation is already allocated.' : `This reservation is ${hold.status}, so it can't be allocated.`,
      })
    }
    if (!RESERVABLE_STATUSES.includes(c.status)) {
      return fail(409, { detail: `Can't allocate for a case that is ${STATUS_LABEL[c.status].toLowerCase()}.` })
    }
    return null
  }
  /** Allocate one hold: the resource is handed over, the need's count goes up, and the case moves as the server moves it. */
  const allocateHold = (c: EmergencyCase, hold: CaseReservation, note: string): CaseAllocation => {
    hold.status = 'allocated'
    const counts = fulfilledByCase.get(c.id) ?? c.items.map(() => 0)
    counts[hold.itemId - 1] += 1
    fulfilledByCase.set(c.id, counts)
    const need = c.items[hold.itemId - 1]!
    if (need.type === 'blood') {
      const unit = units.find((u) => u.status === 'available' && u.group === need.group && u.component === need.component)
      if (unit) unit.status = 'issued'
    }
    const at = new Date().toISOString()
    const allocation: CaseAllocation = {
      id: nextAllocationId++,
      itemId: hold.itemId,
      resource: hold.resource,
      hospital: hold.hospital,
      allocatedBy: role ? NAMES[role] : '',
      at,
      note,
    }
    allocationsByCase.set(c.id, [...(allocationsByCase.get(c.id) ?? []), allocation])
    const complete = c.items.every((item, i) => counts[i] >= item.quantity)
    const left = c.items.reduce((sum, item, i) => sum + item.quantity - counts[i], 0)
    const move = (toStatus: CaseStatus, action: CaseAction) => {
      const entry: StatusChange = { fromStatus: c.status, toStatus, action, note: complete ? 'Every need allocated' : `${left} still to allocate`, actor: null, at }
      histories.set(c.id, [...(histories.get(c.id) ?? []), entry])
      c.status = toStatus
    }
    if (c.status === 'open') move('matching', 'startMatching')
    else if (c.status === 'escalated') move('matching', 'resumeMatching')
    if (c.status === 'matching') move(complete ? 'fulfilled' : 'partiallyFulfilled', complete ? 'fulfil' : 'partiallyFulfil')
    else if (complete && c.status === 'partiallyFulfilled') move('fulfilled', 'fulfil')
    return allocation
  }
  const equipment = sampleEquipment(now)
  const rooms = sampleOperatingRooms(now)
  const bookings = sampleOrBookings(now)
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
  const unitTests = new Map<string, TestResult[]>()
  const unitDetailBody = (unit: BloodUnit) => {
    const tests = unitTests.get(unit.id) ?? []
    const passed = new Set(tests.filter((t) => t.passed).map((t) => t.test))
    return { ...unit, donorId: null, tests, missingTests: REQUIRED_TESTS.map((t) => t.id).filter((id) => !passed.has(id)) }
  }
  let nextId = 100
  let nextAllocationId = 1

  const fetchMock = mockApi({
    'GET /auth/me/': role ? ok(userFor(role)) : fail(403),
    'POST /auth/login/': role ? ok(userFor(role)) : fail(401, { detail: 'That email and password don’t match an account.' }),
    'POST /auth/logout/': { status: 204 },
    'GET /public/status/': erDown ? fail(503) : ok(publicStatus ?? samplePublicStatus(now)),
    'GET /beds/': gate('beds', () => ok(board)),
    'GET /blood/units/': gate('blood', () => ok(units)),
    'POST /blood/units/': edit('blood', ({ body }) => {
      const input = body as BloodUnitInput
      if (units.some((u) => u.id === input.id)) {
        return fail(400, { id: ['A unit with this ID already exists.'] })
      }
      const shelfLifeDays = COMPONENTS.find((c) => c.id === input.component)!.shelfLifeDays
      const created = {
        ...input,
        status: 'quarantined' as const,
        expiresAt: new Date(new Date(input.collectedAt).getTime() + shelfLifeDays * 86_400_000).toISOString(),
      }
      units.push(created)
      return { status: 201, body: created }
    }),
    'GET /blood/units/:id/': ({ params }) => {
      if (!role || role === 'patient' || !canSee(role, 'blood')) return fail(403)
      const unit = units.find((u) => u.id === params.id)
      return unit ? ok(unitDetailBody(unit)) : fail(404)
    },
    'POST /blood/units/:id/tests/': ({ params, body }) => {
      if (!role || role === 'patient' || !canEdit(role, 'blood')) return fail(403)
      const unit = units.find((u) => u.id === params.id)
      if (!unit) return fail(404)
      if (unit.status !== 'quarantined') {
        return fail(409, { detail: `Tests can only be recorded on quarantined units; this one is ${unit.status}.` })
      }
      const { test, passed, reason } = body as { test: ScreeningTest; passed: boolean; reason?: string }
      const existing = unitTests.get(unit.id) ?? []
      if (existing.some((t) => t.test === test)) return fail(400, { test: ['This test is already recorded for this unit.'] })
      if (!passed && !(reason ?? '').trim()) return fail(400, { reason: ['Say why the test failed.'] })
      const updated = [...existing, { test, passed, reason: passed ? '' : (reason ?? ''), recordedAt: new Date().toISOString() }]
      unitTests.set(unit.id, updated)
      const passedTests = new Set(updated.filter((t) => t.passed).map((t) => t.test))
      if (!passed) unit.status = 'discarded'
      else if (REQUIRED_TESTS.every((t) => passedTests.has(t.id))) unit.status = 'available'
      return { status: 201, body: unitDetailBody(unit) }
    },
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

    'GET /emergencies/': view('emergencies', () => ok(cases)),
    'POST /emergencies/': edit('emergencies', ({ body }) => {
      const input = body as CaseInput
      if (!input.items?.length) return fail(400, { items: ['This list may not be empty.'] })
      const year = now.getFullYear()
      const created: EmergencyCase = {
        id: `EC-${year}-${String(cases.length + 1).padStart(4, '0')}`,
        severity: input.severity,
        status: 'open',
        patientRef: input.patientRef,
        hospital: role === 'patient' || !role ? null : userFor(role).hospital,
        createdBy: role ? NAMES[role] : '',
        createdAt: new Date().toISOString(),
        items: input.items,
      }
      cases.push(created)
      histories.set(created.id, [openingEntry(created)])
      cases.sort(byPriority)
      return { status: 201, body: created }
    }),
    // Before /emergencies/:reference/, which would otherwise match "feed".
    'GET /emergencies/feed/': view('emergencies', ({ query }) => {
      const type = query.get('type') ?? 'blood'
      if (type !== 'blood' && type !== 'bed') return fail(400, { type: ['Use one of: blood, bed.'] })
      const entries = customFeed ?? [...cases.map(feedEntryOf), ...sampleNetworkRequests(now)]
      const listed = entries
        .filter((entry) => FEED_STATUSES.includes(entry.status))
        .map((entry) => ({ ...entry, needs: entry.needs.filter((need) => need.type === type) }))
        .filter((entry) => entry.needs.length > 0)
        .sort(byPriority)
      return ok(listed)
    }),
    'GET /emergencies/:reference/': view('emergencies', ({ params }) => {
      const found = findCase(params.reference)
      return found ? ok(detailOf(found)) : fail(404)
    }),
    'GET /emergencies/:reference/candidates/': view('emergencies', ({ params }) => {
      if (!findCase(params.reference)) return fail(404)
      if (customCandidates) return ok({ ...customCandidates, reference: params.reference })
      return ok(sampleCandidates(now)[params.reference] ?? { reference: params.reference, items: [], hospitals: [] })
    }),
    'POST /emergencies/:reference/actions/': edit('emergencies', ({ params, body }) => {
      const found = findCase(params.reference)
      if (!found) return fail(404)
      const { action, note } = body as { action: CaseAction; note: string }
      const next = nextStatus(found.status, action)
      if (!next) return fail(409, { detail: `Can't ${action} a case that is ${STATUS_LABEL[found.status].toLowerCase()}.` })
      if (action === 'close' && !note.trim()) return fail(400, { note: ['Add an outcome note to close the case.'] })
      const entry: StatusChange = {
        fromStatus: found.status,
        toStatus: next,
        action,
        note: note.trim(),
        actor: role ? NAMES[role] : null,
        at: new Date().toISOString(),
      }
      histories.set(found.id, [...(histories.get(found.id) ?? []), entry])
      found.status = next
      return ok(detailOf(found))
    }),

    'POST /emergencies/:reference/reservations/': edit('emergencies', ({ params, body }) => {
      const found = findCase(params.reference)
      if (!found) return fail(404)
      const { itemId, quantity } = body as { itemId: number; quantity: number }
      const need = found.items[itemId - 1]
      if (!need) return fail(400, { itemId: ['No need with that id on this case.'] })
      if (!RESERVABLE_STATUSES.includes(found.status)) {
        return fail(400, { detail: `Can't reserve stock for a case that is ${STATUS_LABEL[found.status].toLowerCase()}.` })
      }
      const remaining = need.quantity - fulfilledFor(found.id, itemId) - heldFor(found.id, itemId)
      if (quantity > remaining) return fail(400, { detail: `Only ${Math.max(remaining, 0)} more can be reserved for this need.` })
      const made = makeHolds(found, itemId, quantity)
      if (made.length === 0) return fail(400, { detail: 'No matching stock is free at this hospital.' })
      return { status: 201, body: made }
    }),
    'POST /emergencies/:reference/reservations/:id/release/': edit('emergencies', ({ params }) => {
      const found = findCase(params.reference)
      if (!found) return fail(404)
      const hold = holdsOf(found.id).find((h) => h.id === Number(params.id))
      if (!hold) return fail(404)
      if (hold.status !== 'held') return fail(409, { detail: `This reservation is ${hold.status}, so it can't be released.` })
      hold.status = 'released'
      stockOf(found)[hold.itemId - 1] += 1
      return ok(hold)
    }),
    // Held reservations across the user's hospital, for the types the role can see (story #46).
    'GET /reservations/': ({ query }) => {
      if (networkDown) return fail(503)
      if (!role || role === 'patient') return fail(403)
      const visible = (Object.keys(TYPE_MODULE) as ResourceType[]).filter((type) => canSee(role, TYPE_MODULE[type]))
      const kind = query.get('type') as ResourceType | null
      if (visible.length === 0 || (kind && !visible.includes(kind))) return fail(403, { detail: 'Your role can’t see this.' })
      const held: HeldReservation[] = [...cases].sort(byPriority).flatMap((c) =>
        holdsOf(c.id)
          .filter((hold) => hold.status === 'held')
          .sort((a, b) => a.expiresAt.localeCompare(b.expiresAt) || a.id - b.id)
          .flatMap((hold) => {
            const need = c.items[hold.itemId - 1]!
            if (!visible.includes(need.type) || (kind && need.type !== kind)) return []
            const fulfilled = fulfilledFor(c.id, hold.itemId)
            return [
              {
                id: hold.id,
                type: need.type,
                status: 'held' as const,
                case: { reference: c.id, severity: c.severity, status: c.status },
                need: { itemId: hold.itemId, label: needLabel(need), quantity: need.quantity, fulfilled, remaining: need.quantity - fulfilled },
                resource: hold.resource,
                expiresAt: hold.expiresAt,
                reservedBy: hold.reservedBy,
                canAllocate: canAllocateHold(c, hold),
              },
            ]
          }),
      )
      return ok(held)
    },
    'POST /reservations/allocate/': ({ body }) => {
      if (networkDown) return fail(503)
      const found = ((body as { ids: number[] }).ids ?? []).map(findHold)
      if (found.length === 0 || found.some((entry) => !entry)) return fail(404, { detail: 'No reservation with one of those ids.' })
      for (const { c, hold } of found as NonNullable<(typeof found)[number]>[]) {
        const refusal = allocationRefusal(c, hold)
        if (refusal) return refusal
      }
      const made = (found as NonNullable<(typeof found)[number]>[]).map(({ c, hold }) => allocateHold(c, hold, ''))
      return { status: 201, body: made }
    },
    'POST /reservations/:id/allocate/': ({ params, body }) => {
      if (networkDown) return fail(503)
      const entry = findHold(Number(params.id))
      if (!entry || !role || role === 'patient') return fail(entry ? 403 : 404)
      const refusal = allocationRefusal(entry.c, entry.hold)
      if (refusal) return refusal
      return { status: 201, body: allocateHold(entry.c, entry.hold, ((body as { note?: string } | undefined)?.note ?? '').trim()) }
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
    'GET /equipment/': view('equipment', () => ok(equipment)),
    'POST /equipment/': edit('equipment', ({ body }) => {
      const input = body as EquipmentInput
      const tag = input.identifier.toUpperCase()
      if (equipment.some((e) => e.identifier === tag)) {
        return fail(400, { identifier: ['This asset tag is already registered in your hospital.'] })
      }
      const created: Equipment = { ...input, identifier: tag, id: nextId++, statusSince: now.toISOString(), hospital: 'CityCare General Hospital' }
      equipment.push(created)
      return { status: 201, body: created }
    }),
    'POST /equipment/:id/actions/': edit('equipment', ({ params, body }) => {
      const index = equipment.findIndex((e) => e.id === Number(params.id))
      if (index < 0) return fail(404)
      try {
        equipment[index] = applyEquipmentAction(equipment[index], (body as { action: EquipmentAction }).action, new Date())
      } catch (error) {
        return fail(409, { detail: (error as Error).message })
      }
      return ok(equipment[index])
    }),
    'GET /operating-rooms/': view('operatingRooms', ({ query }) => {
      const capability = query.get('capability')
      const status = query.get('status')
      return ok(
        rooms.filter(
          (r) => (!capability || r.capabilities.includes(capability as OrCapability)) && (!status || r.status === status),
        ),
      )
    }),
    'POST /operating-rooms/': edit('operatingRooms', ({ body }) => {
      const input = body as OperatingRoomInput
      if (rooms.some((r) => r.name.toLowerCase() === input.name.toLowerCase())) {
        return fail(400, { name: ['A room with this name is already registered in your hospital.'] })
      }
      const created: OperatingRoom = {
        ...input,
        capabilities: [...new Set(input.capabilities)].sort(),
        id: nextId++,
        statusSince: now.toISOString(),
        hospital: 'CityCare General Hospital',
      }
      rooms.push(created)
      return { status: 201, body: created }
    }),
    'GET /operating-rooms/schedule/': view('operatingRooms', ({ query }) => {
      const date = query.get('date') ?? dateKey(now)
      return ok({
        date,
        rooms: rooms.map((room) => ({
          id: room.id,
          name: room.name,
          status: room.status,
          capabilities: room.capabilities,
          bookings: bookings
            .filter((b) => b.roomId === room.id && b.status === 'booked' && b.startsAt.startsWith(date))
            .sort((a, b) => a.startsAt.localeCompare(b.startsAt))
            // Same rule as the server: admins and nurses cancel any booking, others only their own.
            .map((b) => ({ ...b, canCancel: role === 'admin' || role === 'nurse' || b.bookedBy === NAMES[role!] })),
        })),
      })
    }),
    'POST /operating-rooms/bookings/': edit('orBookings', ({ body }) => {
      const input = body as OrBookingInput
      const room = rooms.find((r) => r.id === input.roomId)
      if (!room) return fail(400, { roomId: ['Pick a room.'] })
      const clash = bookings.find(
        (b) => b.roomId === room.id && b.status === 'booked' && b.startsAt < input.endsAt && b.endsAt > input.startsAt,
      )
      if (clash) {
        return fail(400, { startsAt: [`${room.name} is already booked from ${clock(clash.startsAt)} to ${clock(clash.endsAt)}.`] })
      }
      const created: OrBooking = { ...input, id: nextId++, status: 'booked', bookedBy: NAMES.nurse, canCancel: true }
      bookings.push(created)
      return { status: 201, body: created }
    }),
    'POST /operating-rooms/bookings/:id/cancel/': edit('orBookings', ({ params }) => {
      const booking = bookings.find((b) => b.id === Number(params.id))
      if (!booking) return fail(404)
      if (booking.status === 'cancelled') return fail(409, { detail: 'This booking is already cancelled.' })
      booking.status = 'cancelled'
      return ok(booking)
    }),
    'POST /operating-rooms/:id/actions/': edit('operatingRooms', ({ params, body }) => {
      const index = rooms.findIndex((r) => r.id === Number(params.id))
      if (index < 0) return fail(404)
      try {
        rooms[index] = applyOperatingRoomAction(rooms[index], (body as { action: OperatingRoomAction }).action, new Date())
      } catch (error) {
        return fail(409, { detail: (error as Error).message })
      }
      return ok(rooms[index])
    }),
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
  return { fetchMock, board, hospitals, users, cases }
}
