import { useState, type FormEvent } from 'react'
import { BLOOD_GROUPS, type BloodGroup } from '../../api/blood'
import { fieldErrors } from '../../api/client'
import { registerDonor, type Donor } from '../../api/donors'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { firstErrorKey, type FieldErrors } from '../auth/validation'
import { formatGroup } from '../blood/blood'
import styles from './Donors.module.css'
import { statusOf } from './donors'
import { DONOR_FIELD_ORDER, emptyDonor, toDonorInput, validateDonor, type DonorField, type DonorFormValues } from './validation'

/** The element id for each field, so focus can move to the first invalid one. */
const fieldId = (field: DonorField) => `donor-${field}`

type Props = {
  onRegistered: (donor: Donor) => void
  onClose: () => void
}

/** Register a donor (story #20). The API sets the code; the page checks the same rules before sending. */
export function RegisterDonorForm({ onRegistered, onClose }: Props) {
  const [values, setValues] = useState<DonorFormValues>(emptyDonor)
  const [errors, setErrors] = useState<FieldErrors<DonorField>>({})
  const [alert, setAlert] = useState<string>()
  const [pending, setPending] = useState(false)

  const set =
    <K extends DonorField>(key: K) =>
    (value: DonorFormValues[K]) => {
      setValues((v) => ({ ...v, [key]: value }))
      setErrors((e) => ({ ...e, [key]: undefined }))
    }

  /** Moves focus to the first field with an error, and says whether there was one. */
  const focusFirst = (found: FieldErrors<DonorField>) => {
    const first = firstErrorKey(found, DONOR_FIELD_ORDER)
    if (first) document.getElementById(fieldId(first))?.focus()
    return first
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAlert(undefined)
    const found = validateDonor(values)
    setErrors(found)
    if (focusFirst(found)) {
      setAlert('The donor wasn’t registered. Fix the fields marked above.')
      return
    }

    setPending(true)
    try {
      onRegistered(await registerDonor(toDonorInput(values)))
    } catch (error) {
      const status = statusOf(error)
      const server = fieldErrors(error)
      const onFields: FieldErrors<DonorField> = {}
      for (const key of DONOR_FIELD_ORDER) if (server[key]) onFields[key] = server[key]
      setErrors(onFields)
      if (status === 403) {
        setAlert('Your role can’t register donors.')
      } else if (status === 400) {
        focusFirst(onFields)
        setAlert('The donor wasn’t registered. Fix the fields marked above.')
      } else {
        setAlert('The hospital’s system didn’t respond, so the donor wasn’t registered. Try again.')
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <Panel title="Register a donor">
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <TextField
          id={fieldId('fullName')}
          label="Full name"
          hint="Required. Up to 150 characters."
          value={values.fullName}
          onChange={set('fullName')}
          error={errors.fullName}
          autoComplete="off"
          required
        />
        <Field id={fieldId('bloodGroup')} label="Blood group" hint="Required." error={errors.bloodGroup}>
          <select
            id={fieldId('bloodGroup')}
            value={values.bloodGroup}
            required
            aria-invalid={errors.bloodGroup ? true : undefined}
            aria-describedby={errors.bloodGroup ? `${fieldId('bloodGroup')}-error` : undefined}
            onChange={(e) => set('bloodGroup')(e.target.value as '' | BloodGroup)}
          >
            <option value="">Choose a group</option>
            {BLOOD_GROUPS.map((group) => (
              <option key={group} value={group}>
                {formatGroup(group)}
              </option>
            ))}
          </select>
        </Field>
        <TextField
          id={fieldId('phone')}
          label="Phone"
          type="tel"
          optional
          hint="Digits, spaces or dashes, with an optional leading +."
          value={values.phone}
          onChange={set('phone')}
          error={errors.phone}
          autoComplete="off"
        />
        <TextField
          id={fieldId('email')}
          label="Email"
          type="email"
          optional
          value={values.email}
          onChange={set('email')}
          error={errors.email}
          autoComplete="off"
        />
        <FormAlert>{alert}</FormAlert>
        <div className={styles.inline}>
          <Button pending={pending} pendingLabel="Registering…">
            Register donor
          </Button>
          <button type="button" className={styles.back} onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  )
}
