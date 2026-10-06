import { useState } from 'react'
import { Field } from './Field'
import { describedBy, type FieldProps } from './fieldIds'
import styles from './Form.module.css'

type PasswordFieldProps = FieldProps & {
  value: string
  onChange: (value: string) => void
  autoComplete: 'current-password' | 'new-password'
}

export function PasswordField({ value, onChange, autoComplete, ...field }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false)

  return (
    <Field {...field}>
      <div className={styles.inputWrap}>
        <input
          id={field.id}
          className={`${styles.input} ${styles.withToggle}`}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          aria-invalid={field.error ? true : undefined}
          aria-describedby={describedBy(field)}
        />
        <button
          type="button"
          className={styles.toggle}
          aria-pressed={visible}
          aria-controls={field.id}
          aria-label={visible ? 'Hide password' : 'Show password'}
          onClick={() => setVisible((v) => !v)}
        >
          {visible ? 'Hide' : 'Show'}
        </button>
      </div>
    </Field>
  )
}
