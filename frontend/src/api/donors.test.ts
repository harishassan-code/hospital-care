import { afterEach, describe, expect, it, vi } from 'vitest'
import { bookAppointment, cancelAppointment, getDonor, listDonors, recordScreening, registerDonor } from './donors'

const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => {
  vi.restoreAllMocks()
})

describe('donor calls', () => {
  it('searches with the text and group it is given, and nothing else', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, []))
    await listDonors({ q: 'DNR-00002', bloodGroup: 'B+' })
    await listDonors()
    expect(String(fetchMock.mock.calls[0]![0])).toMatch(/\/blood\/donors\/\?q=DNR-00002&bloodGroup=B%2B$/)
    expect(String(fetchMock.mock.calls[1]![0])).toMatch(/\/blood\/donors\/$/)
  })

  it('registers a donor with a POST and returns the code the server set', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(201, { id: 'DNR-00007' }))
    expect(await registerDonor({ fullName: 'Sample Donor Z', bloodGroup: 'O+' })).toEqual({ id: 'DNR-00007' })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toMatch(/\/blood\/donors\/$/)
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({ fullName: 'Sample Donor Z', bloodGroup: 'O+' })
  })

  it('encodes the donor code in the detail and screening paths', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, {}))
    await getDonor('DNR-00002')
    await recordScreening('DNR-00002', { eligible: false, reason: 'Low haemoglobin', deferredUntil: null })
    expect(String(fetchMock.mock.calls[0]![0])).toMatch(/\/blood\/donors\/DNR-00002\/$/)
    const [url, init] = fetchMock.mock.calls[1]!
    expect(String(url)).toMatch(/\/blood\/donors\/DNR-00002\/screening\/$/)
    expect(JSON.parse(String(init?.body))).toEqual({ eligible: false, reason: 'Low haemoglobin', deferredUntil: null })
  })

  it('books with the donor and the start, and cancels by appointment id', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(201, { id: 5 }))
    await bookAppointment({ donorId: 'DNR-00002', startsAt: '2026-10-06T05:00:00.000Z' })
    await cancelAppointment(5)
    expect(JSON.parse(String(fetchMock.mock.calls[0]![1]?.body))).toEqual({
      donorId: 'DNR-00002',
      startsAt: '2026-10-06T05:00:00.000Z',
    })
    expect(String(fetchMock.mock.calls[1]![0])).toMatch(/\/blood\/appointments\/5\/cancel\/$/)
  })
})
