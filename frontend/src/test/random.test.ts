import { describe, expect, it } from 'vitest'
import { seededRandom } from './random'

describe('seededRandom', () => {
  it('repeats the same sequence for the same seed', () => {
    const a = seededRandom(42)
    const b = seededRandom(42)
    expect([a.next(), a.next(), a.next()]).toEqual([b.next(), b.next(), b.next()])
  })

  it('draws integers within inclusive bounds and picks from lists', () => {
    const r = seededRandom(1)
    for (let i = 0; i < 200; i++) {
      const n = r.int(3, 5)
      expect(n).toBeGreaterThanOrEqual(3)
      expect(n).toBeLessThanOrEqual(5)
    }
    expect(['x', 'y']).toContain(r.pick(['x', 'y']))
  })
})
