import { afterEach, describe, expect, it, vi } from 'vitest'
import { listTransfers, postTransferAction, requestTransfer, TRANSFER_ACTION_LABEL, TRANSFER_STATUS_LABEL } from './transfers'

const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => {
  vi.restoreAllMocks()
})

describe('listTransfers', () => {
  it('asks for the direction and status it is given, and nothing else', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, []))
    await listTransfers({ direction: 'outgoing', status: 'inTransit' })
    await listTransfers()
    expect(String(fetchMock.mock.calls[0]![0])).toMatch(/\/transfers\/\?direction=outgoing&status=inTransit$/)
    expect(String(fetchMock.mock.calls[1]![0])).toMatch(/\/transfers\/$/)
  })
})

describe('requestTransfer', () => {
  it('posts the need, the supplier and the quantity, and returns the new transfer', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(201, { id: 9 }))
    expect(await requestTransfer({ itemId: 1, supplierId: 2, quantity: 3 })).toEqual({ id: 9 })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toMatch(/\/transfers\/$/)
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({ itemId: 1, supplierId: 2, quantity: 3 })
  })
})

describe('postTransferAction', () => {
  it('sends the move, and the reason or note only when there is one', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200, { id: 4 }))
    await postTransferAction(4, 'reject', { reason: 'No stock' })
    await postTransferAction(4, 'approve')
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toMatch(/\/transfers\/4\/actions\/$/)
    expect(JSON.parse(String(init?.body))).toEqual({ action: 'reject', reason: 'No stock' })
    expect(JSON.parse(String(fetchMock.mock.calls[1]![1]?.body))).toEqual({ action: 'approve' })
  })
})

describe('labels', () => {
  it('names each status and each move in words the page shows', () => {
    expect(TRANSFER_STATUS_LABEL.inTransit).toBe('In transit')
    expect(TRANSFER_STATUS_LABEL.cancelled).toBe('Cancelled')
    expect(TRANSFER_ACTION_LABEL.startTransit).toBe('Mark in transit')
    expect(TRANSFER_ACTION_LABEL.deliver).toBe('Confirm receipt')
  })
})
