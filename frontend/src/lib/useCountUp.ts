import { useEffect, useRef, useState } from 'react'

function canAnimate(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    typeof window.requestAnimationFrame === 'function' &&
    !window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

/**
 * A number that counts up from 0 to `value` the first time it is shown (about 0.7 s, easing out), then simply follows
 * it, so a live refresh never replays the count. It shows the final number at once when the device asks for reduced
 * motion, and wherever animation isn't available (the test runner, very old browsers).
 */
export function useCountUp(value: number, duration = 700): number {
  const [animate] = useState(canAnimate)
  const [shown, setShown] = useState(animate ? 0 : value)
  const counted = useRef(!animate)

  useEffect(() => {
    if (counted.current) {
      setShown(value)
      return
    }
    let frame = 0
    const start = performance.now()
    const tick = (time: number) => {
      const progress = Math.min(1, (time - start) / duration)
      setShown(Math.round(value * (1 - (1 - progress) ** 3)))
      if (progress < 1) frame = requestAnimationFrame(tick)
      else counted.current = true
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value, duration])

  return shown
}
