import { useEffect, useState } from 'react'
import {
  getBloodUnit,
  recordTest,
  REQUIRED_TESTS,
  type BloodUnit,
  type BloodUnitDetail,
  type ScreeningTest,
} from '../../api/blood'
import { ApiError, fieldErrors } from '../../api/client'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import styles from './Blood.module.css'

type Props = {
  units: BloodUnit[]
  onUpdated: (unit: BloodUnit) => void
}

/** Record screening results on quarantined units (story #18). A fail discards the unit with a reason;
 * passing every required test releases it to available — both happen on the server, not here. */
export function ScreeningPanel({ units, onUpdated }: Props) {
  const quarantined = units.filter((u) => u.status === 'quarantined')
  const [selected, setSelected] = useState('')
  const stillQuarantined = selected !== '' && quarantined.some((u) => u.id === selected)

  return (
    <Panel title="Screening" aside={<span className={styles.note}>{quarantined.length} awaiting testing</span>}>
      {quarantined.length === 0 ? (
        <p className={styles.note}>No units are waiting on screening.</p>
      ) : (
        <>
          <div className={styles.form}>
            <Field id="screening-unit" label="Unit to screen">
              <select id="screening-unit" value={selected} onChange={(e) => setSelected(e.target.value)}>
                <option value="">Choose a unit…</option>
                {quarantined.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.id}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          {stillQuarantined && <UnitScreening key={selected} unitId={selected} onUpdated={onUpdated} onDone={() => setSelected('')} />}
        </>
      )}
    </Panel>
  )
}

function UnitScreening({ unitId, onUpdated, onDone }: { unitId: string; onUpdated: (unit: BloodUnit) => void; onDone: () => void }) {
  const [detail, setDetail] = useState<BloodUnitDetail | null>(null)
  const [failed, setFailed] = useState(false)
  const [failing, setFailing] = useState<ScreeningTest | null>(null)
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState<ScreeningTest | null>(null)
  const [alert, setAlert] = useState<string>()

  useEffect(() => {
    let active = true
    getBloodUnit(unitId)
      .then((data) => active && setDetail(data))
      .catch(() => active && setFailed(true))
    return () => {
      active = false
    }
  }, [unitId])

  async function submit(test: ScreeningTest, passed: boolean) {
    setAlert(undefined)
    if (!passed && !reason.trim()) {
      setAlert('Say why the test failed.')
      return
    }
    setPending(test)
    try {
      const updated = await recordTest(unitId, { test, passed, reason: passed ? '' : reason })
      onUpdated(updated)
      if (updated.status !== 'quarantined') {
        onDone()
        return
      }
      setDetail(updated)
      setFailing(null)
      setReason('')
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      const server = fieldErrors(error)
      if (status === 400 && server.reason) setAlert(server.reason)
      else if (status === 403) setAlert('Your role can’t record screening results.')
      else setAlert('The hospital’s system didn’t respond, so the result wasn’t saved. Try again.')
    } finally {
      setPending(null)
    }
  }

  if (failed) return <p role="alert">Couldn’t load this unit’s screening results. Try again.</p>
  if (!detail) return <p aria-live="polite">Loading…</p>

  const resultFor = (test: ScreeningTest) => detail.tests.find((t) => t.test === test)

  return (
    <div className={styles.screening}>
      <ul className={styles.testList}>
        {REQUIRED_TESTS.map(({ id, label }) => {
          const result = resultFor(id)
          return (
            <li key={id} className={styles.testRow}>
              <span>{label}</span>
              {result ? (
                <StatusBadge tone={result.passed ? 'ok' : 'critical'}>
                  {result.passed ? 'Passed' : `Failed: ${result.reason}`}
                </StatusBadge>
              ) : failing === id ? (
                <div className={styles.failReason}>
                  <TextField id={`${id}-reason`} label="Reason" value={reason} onChange={setReason} autoComplete="off" />
                  <Button type="button" pending={pending === id} pendingLabel="Saving…" onClick={() => submit(id, false)}>
                    Confirm fail
                  </Button>
                  <button type="button" className={styles.back} onClick={() => setFailing(null)}>
                    Cancel
                  </button>
                </div>
              ) : (
                <div className={styles.testActions}>
                  <Button type="button" pending={pending === id} pendingLabel="Saving…" onClick={() => submit(id, true)}>
                    Pass
                  </Button>
                  <button type="button" className={styles.back} onClick={() => setFailing(id)}>
                    Fail
                  </button>
                </div>
              )}
            </li>
          )
        })}
      </ul>
      <FormAlert>{alert}</FormAlert>
    </div>
  )
}
