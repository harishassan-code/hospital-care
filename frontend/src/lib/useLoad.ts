import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../api/client'

export type Loaded<T> = { state: 'loading' } | { state: 'failed'; status: number } | { state: 'ready'; data: T }

/**
 * Load something when the page opens. `load` must be stable (a module function, or useCallback); to load
 * something else, remount with a React key. `setData` replaces the loaded value after a save, so the page
 * doesn't flash back to "Loading…".
 */
export function useLoad<T>(load: () => Promise<T>) {
  const [result, setResult] = useState<Loaded<T>>({ state: 'loading' })

  useEffect(() => {
    let active = true
    load()
      .then((data) => active && setResult({ state: 'ready', data }))
      .catch((error) => active && setResult({ state: 'failed', status: error instanceof ApiError ? error.status : 0 }))
    return () => {
      active = false
    }
  }, [load])

  const setData = useCallback((update: (current: T) => T) => {
    setResult((current) => (current.state === 'ready' ? { state: 'ready', data: update(current.data) } : current))
  }, [])

  return { result, setData }
}
