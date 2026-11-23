import { useState, type FormEvent } from 'react'
import { fieldErrors } from '../../api/client'
import { updateDepartmentStatus, type DepartmentStatus } from '../../api/emergencies'
import { ER_STATUS_LABEL, type ErStatus } from '../../api/public'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatClock } from '../../lib/time'
import { canEdit } from '../staff/roles'
import { useStaff } from '../staff/staffContext'
import styles from './DepartmentStatusPanel.module.css'

const STATUSES = Object.keys(ER_STATUS_LABEL) as ErStatus[]

type Draft = { status: ErStatus; waitMinutes: string; waitingCount: string }

function draftOf(current: DepartmentStatus | null): Draft {
  return {
    status: current?.status ?? 'accepting',
    waitMinutes: current?.waitMinutes == null ? '' : String(current.waitMinutes),
    waitingCount: current?.waitingCount == null ? '' : String(current.waitingCount),
  }
}

/**
 * Our emergency department's public status (B19): what the network's home page and our hospital's page show. Staff
 * who treat patients (admin, doctor, nurse) update it; other roles see it. Hidden for staff with no hospital.
 */
export function DepartmentStatusPanel() {
  const { user, role, data, setDepartmentStatus } = useStaff()
  const current = data?.emergency ?? null
  const editable = canEdit(role, 'emergencies')
  // null while nobody is editing, so the form follows the live figures; a draft once someone starts.
  const [editing, setEditing] = useState<Draft | null>(null)
  const draft = editing ?? draftOf(current)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [pending, setPending] = useState(false)
  const [saved, setSaved] = useState('')

  if (!user.hospital) return null

  function change(update: Partial<Draft>) {
    setSaved('')
    setEditing((d) => ({ ...(d ?? draftOf(current)), ...update }))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const problems: Record<string, string> = {}
    const wait = Number(draft.waitMinutes)
    const waiting = Number(draft.waitingCount)
    if (draft.waitMinutes === '' || !Number.isInteger(wait) || wait < 0) problems.waitMinutes = 'Enter the wait in whole minutes.'
    if (draft.waitingCount === '' || !Number.isInteger(waiting) || waiting < 0) problems.waitingCount = 'Enter how many people are waiting.'
    setErrors(problems)
    if (Object.keys(problems).length) return
    setPending(true)
    try {
      const status = await updateDepartmentStatus({ status: draft.status, waitMinutes: wait, waitingCount: waiting })
      setDepartmentStatus(status)
      setEditing(null)
      setSaved('Saved. The public pages show it now.')
    } catch (error) {
      const fields = fieldErrors(error)
      setErrors(Object.keys(fields).length ? fields : { detail: 'Couldn’t save the status. Try again.' })
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel id="department" title="Our emergency department">
      <div className={styles.summary}>
        {current?.status ? (
          <>
            <StatusBadge tone={current.status === 'accepting' ? 'ok' : 'warning'}>{ER_STATUS_LABEL[current.status]}</StatusBadge>
            <span>
              About <strong>{current.waitMinutes} min</strong> wait · <strong>{current.waitingCount}</strong> waiting
            </span>
            {current.updatedAt && <span className={styles.updated}>Updated {formatClock(new Date(current.updatedAt))}</span>}
          </>
        ) : (
          <span>{user.hospital.name} hasn’t reported its emergency status yet.</span>
        )}
      </div>
      <p className={styles.note}>This is what patients see on the CityCare home page and on {user.hospital.name}’s page.</p>
      {current?.setBySimulation && current.factors && current.factors.length > 0 && (
        <div className={styles.factors}>
          <h3 className={styles.factorsTitle}>Why this wait</h3>
          <ul>
            {current.factors.map((f) => (
              <li key={f.key}>
                <span>
                  {f.label}: <strong>{f.value}</strong>
                </span>
                <span className={f.minutes > 0 ? styles.adds : styles.none}>
                  {f.minutes > 0 ? `+${f.minutes} min` : 'no delay'}
                </span>
              </li>
            ))}
          </ul>
          <p className={styles.note}>Estimated from the department’s queue, staff on duty and beds every few minutes.</p>
        </div>
      )}
      {editable && (
        <form className={styles.form} onSubmit={submit} noValidate>
          <FormAlert>{errors.detail}</FormAlert>
          <Field id="er-status" label="Status" error={errors.status}>
            <select id="er-status" value={draft.status} onChange={(e) => change({ status: e.target.value as ErStatus })}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {ER_STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </Field>
          <TextField
            id="er-waiting"
            label="People waiting"
            type="number"
            inputMode="numeric"
            min={0}
            value={draft.waitingCount}
            onChange={(v) => change({ waitingCount: v })}
            error={errors.waitingCount}
          />
          <TextField
            id="er-wait"
            label="Estimated wait (minutes)"
            type="number"
            inputMode="numeric"
            min={0}
            value={draft.waitMinutes}
            onChange={(v) => change({ waitMinutes: v })}
            error={errors.waitMinutes}
          />
          <div className={styles.actions}>
            <Button pending={pending} pendingLabel="Saving…">
              Update status
            </Button>
          </div>
        </form>
      )}
      <p role="status" className={styles.saved}>
        {saved}
      </p>
    </Panel>
  )
}
