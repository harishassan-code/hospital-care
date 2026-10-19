import { Field } from './Field'
import { describedBy, type FieldProps } from './fieldIds'
import styles from './Form.module.css'

type TextFieldProps = FieldProps & {
  value: string
  onChange: (value: string) => void
  type?: 'text' | 'email' | 'tel' | 'date'
  autoComplete?: string
  inputMode?: 'decimal' | 'text'
}

export function TextField({ value, onChange, type = 'text', autoComplete, inputMode, ...field }: TextFieldProps) {
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
        aria-invalid={field.error ? true : undefined}
        aria-describedby={describedBy(field)}
      />
    </Field>
  )
}
