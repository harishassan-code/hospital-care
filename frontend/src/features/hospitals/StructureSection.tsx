import { useState, type FormEvent } from 'react'
import { ApiError, fieldErrors } from '../../api/client'
import { addStructureItem, removeStructureItem, type StructureKind } from '../../api/hospitals'
import { FormAlert } from '../../components/form/FormAlert'
import { Panel } from '../../components/ui/Panel'
import styles from './Hospitals.module.css'

export type StructureField = {
  key: string
  label: string
  /** A select instead of a text box. Optional: the first option should be the "none" choice with value "". */
  options?: { value: string; label: string }[]
}

type Item = { id: number; name: string }

type StructureSectionProps<T extends Item> = {
  hospitalId: number
  kind: StructureKind
  title: string
  /** e.g. "department", used in button text and messages. */
  noun: string
  items: T[]
  describe: (item: T) => string
  fields: StructureField[]
  editable: boolean
  onAdded: (item: T) => void
  onRemoved: (id: number) => void
}

function failure(error: unknown, doing: string): string {
  const status = error instanceof ApiError ? error.status : 0
  if (status === 403) return 'Your role can’t change this hospital’s structure.'
  const detail = fieldErrors(error).detail
  if ((status === 400 || status === 409) && detail) return detail
  return `The hospital’s system didn’t respond, so nothing was ${doing}. Try again.`
}

/** One part of a hospital's structure (departments, wards or storage locations): the list, plus add/remove for admins. */
export function StructureSection<T extends Item>(props: StructureSectionProps<T>) {
  const { hospitalId, kind, title, noun, items, describe, fields, editable, onAdded, onRemoved } = props
  const blank = Object.fromEntries(fields.map((f) => [f.key, '']))
  const [values, setValues] = useState<Record<string, string>>(blank)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [alert, setAlert] = useState<string>()
  const [status, setStatus] = useState('')
  const [pending, setPending] = useState(false)
  const inputId = (key: string) => `${kind}-${key}`

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAlert(undefined)
    setStatus('')
    const found: Record<string, string> = {}
    for (const f of fields) if (!f.options && !values[f.key].trim()) found[f.key] = `Enter the ${f.label.toLowerCase()}`
    setErrors(found)
    const first = fields.find((f) => found[f.key])
    if (first) return document.getElementById(inputId(first.key))?.focus()

    const data = Object.fromEntries(
      fields.map((f) => [f.key, f.options ? (values[f.key] ? Number(values[f.key]) : null) : values[f.key].trim()]),
    )
    setPending(true)
    try {
      const item = await addStructureItem<T>(hospitalId, kind, data)
      onAdded(item)
      setValues(blank)
      setStatus(`Added ${item.name}.`)
    } catch (error) {
      const server = fieldErrors(error)
      const onFields = Object.fromEntries(fields.filter((f) => server[f.key]).map((f) => [f.key, server[f.key]]))
      setErrors(onFields)
      const firstServer = fields.find((f) => onFields[f.key])
      if (firstServer) document.getElementById(inputId(firstServer.key))?.focus()
      else setAlert(failure(error, 'added'))
    } finally {
      setPending(false)
    }
  }

  async function remove(item: T) {
    setAlert(undefined)
    setStatus('')
    try {
      await removeStructureItem(hospitalId, kind, item.id)
      onRemoved(item.id)
      setStatus(`Removed ${item.name}.`)
    } catch (error) {
      setAlert(failure(error, 'removed'))
    }
  }

  return (
    <Panel title={title} id={kind}>
      {items.length === 0 ? (
        <p>No {title.toLowerCase()} yet.</p>
      ) : (
        <ul className={styles.items}>
          {items.map((item) => (
            <li key={item.id}>
              <span>{describe(item)}</span>
              {editable && (
                <button type="button" className={styles.action} aria-label={`Remove ${item.name}`} onClick={() => remove(item)}>
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <p role="status" aria-live="polite">
        {status}
      </p>
      <FormAlert>{alert}</FormAlert>
      {editable && (
        <form className={styles.addForm} onSubmit={add} noValidate aria-label={`Add a ${noun}`}>
          {fields.map((f) => {
            const id = inputId(f.key)
            const error = errors[f.key]
            const common = {
              id,
              value: values[f.key],
              'aria-invalid': error ? true : undefined,
              'aria-describedby': error ? `${id}-error` : undefined,
            }
            return (
              <div key={f.key}>
                <label htmlFor={id}>
                  {f.label}
                  {f.options ? (
                    <select {...common} className={styles.select} onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}>
                      {f.options.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      {...common}
                      className={styles.input}
                      onChange={(e) => {
                        setValues((v) => ({ ...v, [f.key]: e.target.value }))
                        setErrors((x) => ({ ...x, [f.key]: '' }))
                      }}
                    />
                  )}
                </label>
                {error && (
                  <p id={`${id}-error`} className={styles.fieldError} role="alert">
                    {error}
                  </p>
                )}
              </div>
            )
          })}
          <button type="submit" className={`${styles.action} ${styles.primary}`} disabled={pending}>
            {pending ? 'Adding…' : `Add ${noun}`}
          </button>
        </form>
      )}
    </Panel>
  )
}
