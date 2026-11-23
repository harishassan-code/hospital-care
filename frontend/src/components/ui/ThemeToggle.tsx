import { Moon, Sun } from 'lucide-react'
import { setTheme, useTheme } from '../../lib/theme'
import styles from './ThemeToggle.module.css'

/** Switches between light and dark. Starts on the device's setting; the choice is then remembered in this browser. */
export function ThemeToggle({ className }: { className?: string }) {
  const theme = useTheme()
  const dark = theme === 'dark'
  return (
    <button
      type="button"
      className={`${styles.toggle} ${className ?? ''}`}
      aria-pressed={dark}
      aria-label="Dark mode"
      title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      onClick={() => setTheme(dark ? 'light' : 'dark')}
    >
      <span className={styles.icons} data-dark={dark} aria-hidden="true">
        <Sun className={styles.sun} size={18} strokeWidth={2} />
        <Moon className={styles.moon} size={18} strokeWidth={2} />
      </span>
    </button>
  )
}
