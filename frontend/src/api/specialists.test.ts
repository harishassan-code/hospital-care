import { afterEach, describe, expect, it, vi } from 'vitest'
import { addOnCallWindow, createSpecialist, getSpecialists, removeOnCallWindow, updateSpecialist } from './specialists'

const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => {
  vi.restoreAllMocks()
})

describe('getSpecialists', () => {
  it('asks only for the filters it is given', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, []))
    await getSpecialists({ hospital: 2, specialty: 'Cardiology', availableNow: true })
    await getSpecialists({ availableNow: false })
    await getSpecialists()
    expect(String(fetchMock.mock.calls[0]![0])).toMatch(/\/specialists\/\?hospital=2&specialty=Cardiology&availableNow=true$/)
    expect(String(fetchMock.mock.calls[1]![0])).toMatch(/\/specialists\/$/)
    expect(String(fetchMock.mock.calls[2]![0])).toMatch(/\/specialists\/$/)
  })
})

describe('writes', () => {
  it('posts a new specialist with their hospital', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(201, { id: 9 }))
    expect(await createSpecialist({ name: 'Dr. Omar Sheikh', specialty: 'Cardiology', hospitalId: 2 })).toEqual({ id: 9 })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toMatch(/\/specialists\/$/)
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({ name: 'Dr. Omar Sheikh', specialty: 'Cardiology', hospitalId: 2 })
  })

  it('patches only the changes it is given', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, { id: 4 }))
    await updateSpecialist(4, { isActive: false })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toMatch(/\/specialists\/4\/$/)
    expect(init?.method).toBe('PATCH')
    expect(JSON.parse(String(init?.body))).toEqual({ isActive: false })
  })

  it('posts an on-call window and deletes one by its ids', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(201, { id: 7 }))
    await addOnCallWindow(4, { startsAt: '2030-01-15T20:00:00+05:00', endsAt: '2030-01-16T08:00:00+05:00' })
    await removeOnCallWindow(4, 7)
    const [addUrl, addInit] = fetchMock.mock.calls[0]!
    expect(String(addUrl)).toMatch(/\/specialists\/4\/on-call\/$/)
    expect(addInit?.method).toBe('POST')
    expect(JSON.parse(String(addInit?.body))).toEqual({ startsAt: '2030-01-15T20:00:00+05:00', endsAt: '2030-01-16T08:00:00+05:00' })
    const [removeUrl, removeInit] = fetchMock.mock.calls[1]!
    expect(String(removeUrl)).toMatch(/\/specialists\/4\/on-call\/7\/$/)
    expect(removeInit?.method).toBe('DELETE')
  })
})
