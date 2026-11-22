import { useCallback, useEffect, useState } from 'react'
import { getCommandCentre, type CommandCentre } from '../../api/commandCentre'
import { REFRESH_MS } from './rules'

export type CommandCentreState =
  | { kind: 'loading' }
  /** Nothing has loaded yet, so there is nothing to show but the failure. */
  | { kind: 'failed' }
  /** `stale` is true when the last refresh failed: the figures shown are the last ones that loaded. */
  | { kind: 'ready'; figures: CommandCentre; stale: boolean }

/**
 * The network's figures, loaded when the page opens and read again every `refreshMs` while the tab is visible.
 * Hidden tabs stop polling; showing one again reads at once. The timer and listener go on unmount. A failed refresh
 * keeps the last figures on the page, and the next successful one clears the stale flag.
 */
export function useCommandCentre(refreshMs = REFRESH_MS) {
  const [state, setState] = useState<CommandCentreState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setInterval> | undefined

    const refresh = () => {
      getCommandCentre().then(
        (figures) => {
          if (active) setState({ kind: 'ready', figures, stale: false })
        },
        () => {
          if (!active) return
          setState((current) => (current.kind === 'ready' ? { ...current, stale: true } : { kind: 'failed' }))
        },
      )
    }
    const start = () => {
      if (timer === undefined) timer = setInterval(refresh, refreshMs)
    }
    const stop = () => {
      if (timer !== undefined) clearInterval(timer)
      timer = undefined
    }
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        stop()
      } else {
        refresh()
        start()
      }
    }

    refresh()
    if (document.visibilityState !== 'hidden') start()
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      active = false
      stop()
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [refreshMs, attempt])

  /** Try the first load again after it failed. */
  const retry = useCallback(() => {
    setState({ kind: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  return { state, retry }
}
