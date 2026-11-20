import { afterEach, describe, expect, it, vi } from 'vitest'
import { getAmbulances } from './ambulances'
import { dispatchAmbulance, postTripAction, TRIP_ACTION_LABEL, TRIP_STATUS_LABEL } from './trips'

const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => {
  vi.restoreAllMocks()
})

describe('dispatchAmbulance', () => {
  it('posts the ambulance to the transfer’s trips', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(201, { id: 7 }))
    expect(await dispatchAmbulance(2, 3)).toEqual({ id: 7 })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toMatch(/\/transfers\/2\/trips\/$/)
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({ ambulance: 3 })
  })
})

describe('postTripAction', () => {
  it('posts one step to the trip', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, { id: 7 }))
    await postTripAction(7, 'depart')
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toMatch(/\/trips\/7\/actions\/$/)
    expect(JSON.parse(String(init?.body))).toEqual({ action: 'depart' })
  })
})

describe('getAmbulances filters', () => {
  it('asks for the status and the base hospital it is given, and nothing else', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, []))
    await getAmbulances({ status: 'available', hospitalId: 4 })
    await getAmbulances()
    expect(String(fetchMock.mock.calls[0]![0])).toMatch(/\/ambulances\/\?status=available&hospital=4$/)
    expect(String(fetchMock.mock.calls[1]![0])).toMatch(/\/ambulances\/$/)
  })
})

describe('labels', () => {
  it('names each trip status and step in the words the page shows', () => {
    expect(TRIP_STATUS_LABEL.enRoute).toBe('En route')
    expect(TRIP_ACTION_LABEL.depart).toBe('Mark departed')
    expect(TRIP_ACTION_LABEL.arrive).toBe('Mark arrived')
    expect(TRIP_ACTION_LABEL.complete).toBe('Mark completed')
  })
})
