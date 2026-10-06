import type { ReactNode } from 'react'
import { FieldError } from './Field'
import styles from './Form.module.css'

type CheckboxProps = {
  id: string
  checked: boolean
  onChange: (checked: boolean) => void
  error?: string
  children: ReactNode
}

export function Checkbox({ id, checked, onChange, error, children }: CheckboxProps) {
  return (
    <div className={styles.field}>
      <div className={styles.check}>
        <input
          id={id}
          type="checkbox"
          className={styles.checkbox}
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
        />
        <label htmlFor={id}>{children}</label>
      </div>
      <FieldError id={id}>{error}</FieldError>
    </div>
  )
}
