import { describe, expect, it } from 'vitest'
import { ApiError } from '../../api/client'
import type { AvailableNeed } from '../../api/emergencies'
import type { Transfer } from '../../api/transfers'
import { askableFor, describeTransferMove, statusWord, transferFailure, transferTypeOf } from './transfers'

const need = (overrides: Partial<AvailableNeed> = {}): AvailableNeed =>
  ({
    type: 'blood',
    group: 'O-',
    component: 'redCells',
    quantity: 4,
    itemId: 1,
    fulfilled: 0,
    remaining: 4,
    localAvailable: 1,
    shortfall: 3,
    reserved: 0,
    ...overrides,
  }) as AvailableNeed

const transfer = (overrides: Partial<Transfer>) => overrides as Transfer

describe('transferTypeOf', () => {
  it('moves blood and equipment, and nothing else', () => {
    expect(transferTypeOf(need())).toBe('blood')
    expect(transferTypeOf(need({ type: 'equipment', equipmentType: 'ventilator' }))).toBe('equipment')
    expect(transferTypeOf(need({ type: 'bed', bedType: 'icu' }))).toBeUndefined()
    expect(transferTypeOf(need({ type: 'operatingRoom', capability: 'cardiac' }))).toBeUndefined()
  })
})

describe('askableFor', () => {
  it('is what the need still lacks, less its holds and the requests still waiting for an answer', () => {
    const waiting = [
      transfer({ itemId: 1, status: 'requested', quantity: 2 }),
      transfer({ itemId: 2, status: 'requested', quantity: 5 }),
      transfer({ itemId: 1, status: 'rejected', quantity: 3 }),
      transfer({ itemId: 1, status: 'approved', quantity: 3 }),
    ]
    expect(askableFor(need({ remaining: 4, reserved: 1 }), waiting)).toBe(1)
  })

  it('is never negative', () => {
    expect(askableFor(need({ remaining: 2, reserved: 3 }), [])).toBe(0)
  })
})

describe('describeTransferMove', () => {
  it('names the request itself, then each later move by its two statuses', () => {
    expect(describeTransferMove({ fromStatus: '', toStatus: 'requested', action: 'request', note: '', actor: null, at: '' })).toBe('Requested')
    expect(describeTransferMove({ fromStatus: 'approved', toStatus: 'inTransit', action: 'startTransit', note: '', actor: null, at: '' })).toBe(
      'Approved → In transit',
    )
  })
})

describe('statusWord', () => {
  it('gives a known status in words, and passes an unknown one through', () => {
    expect(statusWord('inTransit')).toBe('In transit')
    expect(statusWord('archived')).toBe('archived')
    expect(statusWord('constructor')).toBe('constructor')
  })
})

describe('transferFailure', () => {
  const refused = (status: number, body: unknown) => new ApiError(status, body)

  it('shows the server’s detail for a refusal', () => {
    expect(transferFailure(refused(409, { detail: 'No units are free right now.' }))).toBe('No units are free right now.')
  })

  it('shows the server’s field messages when it refuses a field', () => {
    expect(transferFailure(refused(400, { reason: ['Say why this request is rejected.'] }))).toBe('Say why this request is rejected.')
  })

  it('says nothing changed when a refusal has no words of its own', () => {
    expect(transferFailure(refused(400, null))).toBe('Nothing changed. Check the details and try again.')
  })

  it('gives the generic line for a server error or no answer at all', () => {
    const generic = 'The hospital’s system didn’t respond, so nothing changed. Try again.'
    expect(transferFailure(refused(500, { detail: 'boom' }))).toBe(generic)
    expect(transferFailure(new ApiError(0))).toBe(generic)
    expect(transferFailure(new TypeError('network'))).toBe(generic)
  })
})
