import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * Scrolls to the element named by the URL hash (e.g. /staff#attention). Browsers only do this on a
 * full page load; in-app navigation needs it done by hand, once the target has rendered (`ready`).
 */
export function useScrollToHash(ready: boolean) {
  const { hash } = useLocation()
  useEffect(() => {
    if (ready && hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView?.()
  }, [ready, hash])
}
