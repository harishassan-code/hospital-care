import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useCountUp } from './useCountUp'

function motion(reduced: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: reduced && query.includes('reduce'), media: query }))
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('useCountUp (overview tiles)', () => {
  it('shows the number at once where animation is not available, as in this test runner', () => {
    const { result } = renderHook(() => useCountUp(42))
    expect(result.current).toBe(42)
  })

  it('shows the number at once when the device asks for reduced motion', () => {
    motion(true)
    const { result } = renderHook(() => useCountUp(42))
    expect(result.current).toBe(42)
  })

  it('counts up from 0 to the number, then follows later changes without counting again', () => {
    motion(false)
    vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance'] })
    const { result, rerender } = renderHook(({ value }) => useCountUp(value, 700), { initialProps: { value: 100 } })
    expect(result.current).toBe(0)
    act(() => vi.advanceTimersByTime(350))
    expect(result.current).toBeGreaterThan(0)
    expect(result.current).toBeLessThan(100)
    act(() => vi.advanceTimersByTime(500))
    expect(result.current).toBe(100)
    rerender({ value: 120 })
    expect(result.current).toBe(120)
  })
})
