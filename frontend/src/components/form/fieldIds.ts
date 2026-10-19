export type FieldProps = {
  id: string
  label: string
  error?: string
  hint?: string
  optional?: boolean
}

/** Ids to put in aria-describedby so screen readers read the hint and error with the input. */
export function describedBy({ id, error, hint }: FieldProps): string | undefined {
  const ids = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean)
  return ids.length ? ids.join(' ') : undefined
}
