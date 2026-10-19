import type { ReactNode } from 'react'
import styles from './Form.module.css'

/** Form-level error (e.g. the server rejected the login). role="alert" is announced when inserted. */
export function FormAlert({ children }: { children?: ReactNode }) {
  if (!children) return null
  return (
    <div role="alert" className={styles.alert}>
      {children}
    </div>
  )
}
