import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { BedType } from '../../api/beds'
import { BLOOD_GROUPS, COMPONENTS, type BloodGroup, type Component } from '../../api/blood'
import { ApiError } from '../../api/client'
import { createCase, MAX_NEEDS, SEVERITIES, type EmergencyCase } from '../../api/emergencies'
import type { EquipmentType } from '../../api/equipment'
import { OR_CAPABILITIES, type OrCapability } from '../../api/operatingRooms'
import { Button } from '../../components/form/Button'
import { Field, FieldError } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { TYPE_LABEL } from '../beds/beds'
import { formatGroup } from '../blood/blood'
import {
  describeNeed,
  EQUIPMENT_NEED_LABEL,
  emptyCase,
  hasErrors,
  newNeed,
  serverErrors,
  STEPS,
  stepWithErrors,
  toCaseInput,
  toNeed,
  validateCaseStep,
  validateNeedsStep,
  type CaseErrors,
  type CaseFormValues,
  type NeedDraft,
} from './emergencies'
import styles from './Emergencies.module.css'

type Props = { onCreated: (created: EmergencyCase) => void; onClose: () => void }

const FIX_FIELDS = 'The case wasn’t opened. Fix the fields marked below.'

/** Open an emergency case in three steps: the case, what it needs, review (stories #30, #32). */
export function NewCaseForm({ onCreated, onClose }: Props) {
  const [values, setValues] = useState<CaseFormValues>(emptyCase)
  const [errors, setErrors] = useState<CaseErrors>({})
  const [step, setStep] = useState(0)
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)
  const nextKey = useRef(2)
  const stepHeading = useRef<HTMLHeadingElement>(null)

  // Focus the step's heading when the form opens and on every step, so keyboard and screen-reader users
  // land at its start (the "New case" button they pressed is gone).
  useEffect(() => {
    stepHeading.current?.focus()
  }, [step])

  const update = (change: Partial<CaseFormValues>, clear: string[]) => {
    setValues((v) => ({ ...v, ...change }))
    setErrors((e) => ({ ...e, ...Object.fromEntries(clear.map((k) => [k, undefined])) }))
  }

  const updateNeed = (key: number, change: Partial<NeedDraft>) =>
    update({ needs: values.needs.map((n) => (n.key === key ? { ...n, ...change } : n)) }, [`quantity-${key}`, 'needs'])

  const addNeed = () => update({ needs: [...values.needs, newNeed(nextKey.current++)] }, ['needs'])
  const removeNeed = (key: number) => update({ needs: values.needs.filter((n) => n.key !== key) }, [`quantity-${key}`, 'needs'])

  function goTo(next: number) {
    setAlert(undefined)
    setStep(next)
  }

  async function submit() {
    setPending(true)
    try {
      onCreated(await createCase(toCaseInput(values)))
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0
      const found = serverErrors(error, values.needs)
      const back = stepWithErrors(found)
      if (status === 400 && back !== null) {
        setErrors(found)
        setStep(back)
        setAlert(FIX_FIELDS)
      } else if (status === 403) {
        setAlert('Your role can’t open emergency cases.')
      } else {
        setAlert('The hospital’s system didn’t respond, so the case wasn’t opened. Try again.')
      }
    } finally {
      setPending(false)
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (step === 2) {
      void submit()
      return
    }
    const found = step === 0 ? validateCaseStep(values) : validateNeedsStep(values)
    setErrors(found)
    if (hasErrors(found)) {
      setAlert(FIX_FIELDS)
      const first = Object.keys(found).find((k) => found[k])
      const target = first === 'severity' ? `severity-${SEVERITIES[0].id}` : first === 'needs' ? 'add-need' : first
      if (target) document.getElementById(target)?.focus()
      return
    }
    goTo(step + 1)
  }

  return (
    <Panel title="New emergency case">
      <ol className={styles.steps}>
        {STEPS.map((label, i) => (
          <li key={label} aria-current={i === step ? 'step' : undefined} className={i < step ? styles.done : undefined}>
            {label}
          </li>
        ))}
      </ol>
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <h3 ref={stepHeading} tabIndex={-1} className={styles.stepHeading}>
          Step {step + 1} of {STEPS.length}: {STEPS[step]}
        </h3>

        {step === 0 && (
          <>
            <fieldset className={styles.fieldset} aria-describedby={errors.severity ? 'severity-error' : undefined}>
              <legend>Severity</legend>
              <div className={styles.severities}>
                {SEVERITIES.map((s) => (
                  <label key={s.id} className={styles.severity} data-severity={s.id}>
                    <input
                      id={`severity-${s.id}`}
                      type="radio"
                      name="severity"
                      value={s.id}
                      checked={values.severity === s.id}
                      onChange={() => update({ severity: s.id }, ['severity'])}
                    />
                    <span>
                      <strong>{s.label}</strong>
                      <span className={styles.hint}>{s.hint}</span>
                    </span>
                  </label>
                ))}
              </div>
              <FieldError id="severity">{errors.severity}</FieldError>
            </fieldset>
            <TextField
              id="patientRef"
              label="Patient reference"
              optional
              hint="A bed or triage tag, e.g. “Bay 4”. Never the patient’s name or ID number."
              value={values.patientRef}
              onChange={(patientRef) => update({ patientRef }, ['patientRef'])}
              error={errors.patientRef}
              autoComplete="off"
            />
          </>
        )}

        {step === 1 && (
          <>
            {values.needs.map((need, i) => (
              <NeedRow
                key={need.key}
                need={need}
                index={i}
                errors={errors}
                onChange={(change) => updateNeed(need.key, change)}
                onRemove={values.needs.length > 1 ? () => removeNeed(need.key) : undefined}
              />
            ))}
            <div>
              <button
                id="add-need"
                type="button"
                className={styles.secondaryAction}
                onClick={addNeed}
                disabled={values.needs.length >= MAX_NEEDS}
                aria-describedby={errors.needs ? 'needs-error' : undefined}
              >
                Add another need
              </button>
              <FieldError id="needs">{errors.needs}</FieldError>
            </div>
          </>
        )}

        {step === 2 && (
          <dl className={styles.review}>
            <dt>Severity</dt>
            <dd>{SEVERITIES.find((s) => s.id === values.severity)?.label}</dd>
            <dt>Patient reference</dt>
            <dd>{values.patientRef.trim() || 'None'}</dd>
            <dt>Needs</dt>
            <dd>
              <ul>
                {values.needs.map((n) => (
                  <li key={n.key}>{describeNeed(toNeed(n))}</li>
                ))}
              </ul>
            </dd>
          </dl>
        )}

        <FormAlert>{alert}</FormAlert>
        <div className={styles.actions}>
          {step < 2 ? (
            <Button>Next</Button>
          ) : (
            <Button pending={pending} pendingLabel="Opening…">
              Open case
            </Button>
          )}
          {step > 0 && (
            <button type="button" className={styles.secondaryAction} onClick={() => goTo(step - 1)}>
              Back
            </button>
          )}
          <button type="button" className={styles.link} onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  )
}

/** What each type of need is counted in, for the quantity field's label. */
const QUANTITY_LABEL: Record<NeedDraft['type'], string> = { blood: 'Units', bed: 'Beds', equipment: 'Pieces', operatingRoom: 'Rooms' }

type NeedRowProps = {
  need: NeedDraft
  index: number
  /** The form's errors; this row reads its own, keyed `<field>-<key>`. */
  errors: CaseErrors
  onChange: (change: Partial<NeedDraft>) => void
  onRemove?: () => void
}

function NeedRow({ need, index, errors, onChange, onRemove }: NeedRowProps) {
  const id = (field: string) => `${field}-${need.key}`
  const error = (field: string) => errors[id(field)]
  /** A select's error is announced with it, as a text input's is. */
  const selectError = (field: string) => ({
    'aria-invalid': error(field) ? true : undefined,
    'aria-describedby': error(field) ? `${id(field)}-error` : undefined,
  })
  return (
    <fieldset className={styles.need}>
      <legend>Need {index + 1}</legend>
      <div className={styles.needFields}>
        <Field id={id('type')} label="Type">
          <select id={id('type')} {...selectError('type')} value={need.type} onChange={(e) => onChange({ type: e.target.value as NeedDraft['type'] })}>
            <option value="blood">Blood</option>
            <option value="bed">Bed</option>
            <option value="equipment">Equipment</option>
            <option value="operatingRoom">Operating room</option>
          </select>
        </Field>
        {need.type === 'blood' && (
          <>
            <Field id={id('group')} label="Blood group" error={error('group')}>
              <select id={id('group')} {...selectError('group')} value={need.group} onChange={(e) => onChange({ group: e.target.value as BloodGroup })}>
                {BLOOD_GROUPS.map((g) => (
                  <option key={g} value={g}>
                    {formatGroup(g)}
                  </option>
                ))}
              </select>
            </Field>
            <Field id={id('component')} label="Component" error={error('component')}>
              <select id={id('component')} {...selectError('component')} value={need.component} onChange={(e) => onChange({ component: e.target.value as Component })}>
                {COMPONENTS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </Field>
          </>
        )}
        {need.type === 'bed' && (
          <Field id={id('bedType')} label="Bed type" error={error('bedType')}>
            <select id={id('bedType')} {...selectError('bedType')} value={need.bedType} onChange={(e) => onChange({ bedType: e.target.value as BedType })}>
              {(Object.keys(TYPE_LABEL) as BedType[]).map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABEL[t]}
                </option>
              ))}
            </select>
          </Field>
        )}
        {need.type === 'equipment' && (
          <Field id={id('equipmentType')} label="Equipment" error={error('equipmentType')}>
            <select
              id={id('equipmentType')} {...selectError('equipmentType')}
              value={need.equipmentType}
              onChange={(e) => onChange({ equipmentType: e.target.value as EquipmentType })}
            >
              {(Object.keys(EQUIPMENT_NEED_LABEL) as EquipmentType[]).map((t) => (
                <option key={t} value={t}>
                  {EQUIPMENT_NEED_LABEL[t]}
                </option>
              ))}
            </select>
          </Field>
        )}
        {need.type === 'operatingRoom' && (
          <Field id={id('capability')} label="Capability" error={error('capability')}>
            <select id={id('capability')} {...selectError('capability')} value={need.capability} onChange={(e) => onChange({ capability: e.target.value as OrCapability })}>
              {OR_CAPABILITIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </Field>
        )}
        <TextField
          id={id('quantity')}
          label={QUANTITY_LABEL[need.type]}
          inputMode="numeric"
          value={need.quantity}
          onChange={(quantity) => onChange({ quantity })}
          error={error('quantity')}
        />
      </div>
      {onRemove && (
        <button type="button" className={styles.link} onClick={onRemove}>
          Remove need {index + 1}
        </button>
      )}
    </fieldset>
  )
}
