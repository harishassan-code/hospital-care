import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { currentTheme, THEME_KEY } from '../../lib/theme'
import { ThemeToggle } from './ThemeToggle'

type Listener = () => void

/** A device colour setting the test can flip, as matchMedia would report it. */
function device(dark: boolean) {
  const listeners = new Set<Listener>()
  const query = {
    get matches() {
      return dark
    },
    media: '(prefers-color-scheme: dark)',
    addEventListener: (_: string, listener: Listener) => listeners.add(listener),
    removeEventListener: (_: string, listener: Listener) => listeners.delete(listener),
  }
  vi.stubGlobal('matchMedia', () => query)
  return {
    turn(next: boolean) {
      dark = next
      listeners.forEach((listener) => listener())
    },
  }
}

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

afterEach(() => vi.unstubAllGlobals())

describe('ThemeToggle (light and dark mode)', () => {
  it('starts on the device setting', () => {
    device(true)
    render(<ThemeToggle />)
    expect(screen.getByRole('button', { name: 'Dark mode' })).toHaveAttribute('aria-pressed', 'true')
    expect(currentTheme()).toBe('dark')
  })

  it('switches theme, applies it to the page and remembers the choice', async () => {
    device(false)
    render(<ThemeToggle />)
    const toggle = screen.getByRole('button', { name: 'Dark mode' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')

    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')

    await userEvent.click(toggle)
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem(THEME_KEY)).toBe('light')
  })

  it('a saved choice wins over the device setting', () => {
    device(true)
    localStorage.setItem(THEME_KEY, 'light')
    render(<ThemeToggle />)
    expect(screen.getByRole('button', { name: 'Dark mode' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('follows the device while nothing is chosen, and stops once the user picks', async () => {
    const settings = device(false)
    render(<ThemeToggle />)
    const toggle = screen.getByRole('button', { name: 'Dark mode' })
    act(() => settings.turn(true))
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(document.documentElement.dataset.theme).toBe('dark')

    await userEvent.click(toggle) // the user picks light
    act(() => settings.turn(true))
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
  })
})
