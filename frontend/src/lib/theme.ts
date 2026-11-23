import { useSyncExternalStore } from 'react'

/**
 * Light or dark. The device's setting decides until the user picks one with the toggle; that choice is kept in this
 * browser. index.html runs the same rule before the first paint, so the page never flashes the wrong theme.
 */
export type Theme = 'light' | 'dark'

export const THEME_KEY = 'citycare-theme'
const DARK_QUERY = '(prefers-color-scheme: dark)'
const listeners = new Set<() => void>()

function media(): MediaQueryList | null {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' ? window.matchMedia(DARK_QUERY) : null
}

export function savedTheme(): Theme | null {
  try {
    const value = window.localStorage.getItem(THEME_KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null // storage blocked (private mode): fall back to the device
  }
}

export function systemTheme(): Theme {
  return media()?.matches ? 'dark' : 'light'
}

export function currentTheme(): Theme {
  return savedTheme() ?? systemTheme()
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme
}

function notify() {
  apply(currentTheme())
  listeners.forEach((listener) => listener())
}

/** Picks a theme and remembers it. Colours cross-fade briefly, unless the device asks for reduced motion. */
export function setTheme(theme: Theme) {
  try {
    window.localStorage.setItem(THEME_KEY, theme)
  } catch {
    // storage blocked: the choice lasts until the page is reloaded
  }
  const root = document.documentElement
  root.classList.add('theme-transition')
  window.setTimeout(() => root.classList.remove('theme-transition'), 350)
  notify()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  // Follow the device while the user hasn't picked a theme (e.g. a phone that turns dark at sunset).
  const query = media()
  const onSystemChange = () => {
    if (!savedTheme()) notify()
  }
  query?.addEventListener?.('change', onSystemChange)
  return () => {
    listeners.delete(listener)
    query?.removeEventListener?.('change', onSystemChange)
  }
}

/** The theme in force, re-rendering when it changes. */
export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, currentTheme, () => 'light')
}
