import { Field } from './Field'
import { describedBy, type FieldProps } from './fieldIds'
import styles from './Form.module.css'

type TextFieldProps = FieldProps & {
  value: string
  onChange: (value: string) => void
  type?: 'text' | 'email' | 'tel' | 'date' | 'number' | 'time'
  autoComplete?: string
  inputMode?: 'decimal' | 'numeric' | 'text'
  required?: boolean
  min?: number
  max?: number
}

export function TextField({ value, onChange, type = 'text', autoComplete, inputMode, required, min, max, ...field }: TextFieldProps) {
  return (
    <Field {...field}>
      <input
        id={field.id}
        className={styles.input}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        inputMode={inputMode}
        required={required}
        min={min}
        max={max}
        aria-invalid={field.error ? true : undefined}
        aria-describedby={describedBy(field)}
      />
    </Field>
  )
}
