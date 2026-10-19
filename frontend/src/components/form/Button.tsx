import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import styles from './Form.module.css'

type Variant = 'primary' | 'secondary'

type ButtonProps = {
  children: ReactNode
  type?: 'button' | 'submit'
  pending?: boolean
  /** Shown instead of children while pending, e.g. "Logging in…" */
  pendingLabel?: string
  onClick?: () => void
}

export function Button({ children, type = 'submit', pending = false, pendingLabel, onClick }: ButtonProps) {
  return (
    <button type={type} className={styles.button} disabled={pending} aria-busy={pending} onClick={onClick}>
      {pending && pendingLabel ? pendingLabel : children}
    </button>
  )
}

export function ButtonLink({ to, children, variant = 'primary' }: { to: string; children: ReactNode; variant?: Variant }) {
  return (
    <Link to={to} className={`${styles.button} ${variant === 'secondary' ? styles.secondary : ''}`}>
      {children}
    </Link>
  )
}
