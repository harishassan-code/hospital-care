import { useState, type FormEvent } from 'react'
import { AuthError, authErrorMessage } from '../../api/auth'
import { firstErrorKey, type FieldErrors } from './validation'

type UseAuthFormOptions<V> = {
  initial: V
  validate: (values: V) => FieldErrors<keyof V & string>
  /** Field keys in on-screen order. Each input's id must equal its key so focus can find it. */
  order: readonly (keyof V & string)[]
  onValid: (values: V) => Promise<void>
}

/**
 * Shared state and submit flow for the log-in and sign-up forms: client-side validation,
 * focus on the first invalid field, a pending flag, and a plain message when the server says no.
 */
export function useAuthForm<V extends object>({ initial, validate, order, onValid }: UseAuthFormOptions<V>) {
  const [values, setValues] = useState(initial)
  const [errors, setErrors] = useState<FieldErrors<keyof V & string>>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)

  const field =
    <K extends keyof V & string>(key: K) =>
    (value: V[K]) => {
      setValues((v) => ({ ...v, [key]: value }))
      setErrors((e) => ({ ...e, [key]: undefined }))
    }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAlert(undefined)
    const found = validate(values)
    setErrors(found)
    const first = firstErrorKey(found, order)
    if (first) {
      ;(event.currentTarget.elements.namedItem(first) as HTMLElement | null)?.focus()
      return
    }
    setPending(true)
    try {
      await onValid(values)
    } catch (error) {
      setAlert(authErrorMessage(error instanceof AuthError ? error.kind : 'unavailable'))
    } finally {
      setPending(false)
    }
  }

  return { values, errors, alert, pending, field, handleSubmit }
}
