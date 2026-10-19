import type { ReactNode } from 'react'
import type { FieldProps } from './fieldIds'
import styles from './Form.module.css'

export function FieldError({ id, children }: { id: string; children?: string }) {
  if (!children) return null
  return (
    <p className={styles.error} id={`${id}-error`}>
      <span className={styles.errorMark} aria-hidden="true">
        !
      </span>
      {children}
    </p>
  )
}

/** Label, hint and error around a control. */
export function Field({ id, label, error, hint, optional, children }: FieldProps & { children: ReactNode }) {
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={id}>
        {label}
        {optional && <span className={styles.optional}> (optional)</span>}
      </label>
      {hint && (
        <p className={styles.hint} id={`${id}-hint`}>
          {hint}
        </p>
      )}
      {children}
      <FieldError id={id}>{error}</FieldError>
    </div>
  )
}
