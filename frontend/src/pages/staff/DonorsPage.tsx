import { useState, type FormEvent } from 'react'
import { BLOOD_GROUPS, type BloodGroup } from '../../api/blood'
import { ApiError, fieldErrors } from '../../api/client'
import {
  bookAppointment,
  cancelAppointment,
  getAppointments,
  getDonors,
  recordScreening,
  registerDonor,
  type Appointment,
  type Donor,
} from '../../api/donors'
import { Button } from '../../components/form/Button'
import { Field } from '../../components/form/Field'
import { FormAlert } from '../../components/form/FormAlert'
import { TextField } from '../../components/form/TextField'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import formStyles from '../../features/blood/Blood.module.css'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

const message = (error: unknown, fallback: string) => {
  const found = fieldErrors(error)
  const first = Object.values(found)[0]
  if (first) return first
  if (error instanceof ApiError && error.status === 403) return 'Your role can’t do this.'
  return fallback
}

/** Donors (stories #20 to #22): register, screen and book donation appointments. */
export default function DonorsPage() {
  const { role } = useStaff()
  const donors = useLoad(getDonors)
  const appointments = useLoad(getAppointments)
  const [query, setQuery] = useState('')
  const [group, setGroup] = useState<'all' | BloodGroup>('all')
  const [selected, setSelected] = useState<Donor>()
  const [notice, setNotice] = useState<string>()

  if (donors.result.state !== 'ready') return <StaffDataState failed={donors.result.state === 'failed'} />
  const editable = canEdit(role, 'blood')
  const q = query.trim().toLowerCase()
  const shown = donors.result.data.filter(
    (d) => (group === 'all' || d.bloodGroup === group) && (!q || d.fullName.toLowerCase().includes(q) || d.id.toLowerCase().includes(q)),
  )
  const upsert = (donor: Donor) => {
    donors.setData((current) => (current.some((d) => d.id === donor.id) ? current.map((d) => (d.id === donor.id ? donor : d)) : [donor, ...current]))
    setSelected(donor)
  }

  return (
    <div className={pageStyles.stack}>
      {editable && (
        <RegisterDonor
          onRegistered={(donor) => {
            upsert(donor)
            setNotice(`Registered ${donor.fullName}. Donor code ${donor.id}.`)
          }}
        />
      )}
      <p role="status">{notice}</p>
      <Panel title="Donors">
        <div className={pageStyles.toolbar}>
          <TextField id="donor-search" label="Search by name or code" optional value={query} onChange={setQuery} />
          <Field id="donor-group" label="Blood group">
            <select id="donor-group" value={group} onChange={(e) => setGroup(e.target.value as 'all' | BloodGroup)}>
              <option value="all">All</option>
              {BLOOD_GROUPS.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </Field>
        </div>
        {shown.length === 0 ? (
          <p>No donors match.</p>
        ) : (
          <div className="table-scroll">
            <table aria-label="Donors">
              <thead>
                <tr>
                  <th scope="col">Code</th>
                  <th scope="col">Name</th>
                  <th scope="col">Group</th>
                  <th scope="col">Eligibility</th>
                  {editable && <th scope="col">Open</th>}
                </tr>
              </thead>
              <tbody>
                {shown.map((d) => (
                  <tr key={d.id}>
                    <th scope="row">{d.id}</th>
                    <td>{d.fullName}</td>
                    <td>{d.bloodGroup}</td>
                    <td>
                      {d.eligible ? (
                        <StatusBadge tone="ok">Eligible</StatusBadge>
                      ) : (
                        <StatusBadge tone="warning">
                          {`Deferred${d.eligibleFrom ? ` until ${d.eligibleFrom.slice(0, 10)}` : ''}`}
                        </StatusBadge>
                      )}
                    </td>
                    {editable && (
                      <td>
                        <button type="button" className={formStyles.more} onClick={() => setSelected(d)} aria-label={`Open ${d.fullName}`}>
                          Open
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {editable && selected && (
        <DonorDetail
          key={selected.id}
          donor={selected}
          onScreened={upsert}
          onBooked={(a) => appointments.setData((current) => [...current, a])}
        />
      )}
      {appointments.result.state === 'ready' && (
        <Appointments
          items={appointments.result.data}
          editable={editable}
          onCancelled={(a) => appointments.setData((current) => current.filter((x) => x.id !== a.id))}
        />
      )}
    </div>
  )
}

function RegisterDonor({ onRegistered }: { onRegistered: (d: Donor) => void }) {
  const [open, setOpen] = useState(false)
  const [fullName, setFullName] = useState('')
  const [bloodGroup, setBloodGroup] = useState<BloodGroup>('O+')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState<string>()
  const [pending, setPending] = useState(false)

  if (!open) {
    return (
      <button type="button" className={formStyles.more} onClick={() => setOpen(true)}>
        Register donor
      </button>
    )
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!fullName.trim()) return setError('Enter the donor’s full name.')
    setPending(true)
    setError(undefined)
    try {
      onRegistered(await registerDonor({ fullName: fullName.trim(), bloodGroup, phone: phone.trim(), email: '' }))
      setOpen(false)
      setFullName('')
      setPhone('')
    } catch (err) {
      setError(message(err, 'The donor wasn’t registered. Try again.'))
    } finally {
      setPending(false)
    }
  }
  return (
    <Panel title="Register donor">
      <form className={formStyles.form} onSubmit={submit} noValidate>
        <TextField id="fullName" label="Full name" value={fullName} onChange={setFullName} />
        <Field id="bloodGroup" label="Blood group">
          <select id="bloodGroup" value={bloodGroup} onChange={(e) => setBloodGroup(e.target.value as BloodGroup)}>
            {BLOOD_GROUPS.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </Field>
        <TextField id="phone" label="Phone" type="tel" optional value={phone} onChange={setPhone} />
        <FormAlert>{error}</FormAlert>
        <div className={formStyles.formActions}>
          <Button pending={pending} pendingLabel="Registering…">
            Register donor
          </Button>
          <button type="button" className={formStyles.more} onClick={() => setOpen(false)}>
            Cancel
          </button>
        </div>
      </form>
    </Panel>
  )
}

function DonorDetail({ donor, onScreened, onBooked }: { donor: Donor; onScreened: (d: Donor) => void; onBooked: (a: Appointment) => void }) {
  const [reason, setReason] = useState('')
  const [until, setUntil] = useState('')
  const [slot, setSlot] = useState('')
  const [error, setError] = useState<string>()

  const screen = async (eligible: boolean) => {
    setError(undefined)
    if (!eligible && !reason.trim()) return setError('Give the deferral reason.')
    try {
      onScreened(await recordScreening(donor.id, { eligible, reason: eligible ? '' : reason.trim(), deferredUntil: eligible || !until ? null : until }))
    } catch (err) {
      setError(message(err, 'The screening wasn’t saved. Try again.'))
    }
  }
  const book = async () => {
    setError(undefined)
    if (!slot) return setError('Choose a date and time.')
    try {
      onBooked(await bookAppointment(donor.id, new Date(slot).toISOString()))
      setSlot('')
    } catch (err) {
      setError(message(err, 'The appointment wasn’t booked. Try again.'))
    }
  }

  return (
    <Panel title={`${donor.fullName} (${donor.id})`}>
      <p>
        {donor.bloodGroup} ·{' '}
        {donor.eligible ? 'Eligible to donate' : `Deferred${donor.ineligibleReason ? `: ${donor.ineligibleReason}` : ''}`}
      </p>
      <div className={formStyles.form}>
        <TextField id="deferral-reason" label="Deferral reason" optional value={reason} onChange={setReason} />
        <TextField id="deferred-until" label="Deferred until" type="date" optional value={until} onChange={setUntil} />
        <div className={formStyles.formActions}>
          <button type="button" className={formStyles.more} onClick={() => screen(true)}>
            Record pass
          </button>
          <button type="button" className={formStyles.more} onClick={() => screen(false)}>
            Record deferral
          </button>
        </div>
        <Field id="slot" label="Appointment">
          <input id="slot" type="datetime-local" value={slot} onChange={(e) => setSlot(e.target.value)} />
        </Field>
        <div className={formStyles.formActions}>
          <button type="button" className={formStyles.more} onClick={book} disabled={!donor.eligible}>
            Book appointment
          </button>
        </div>
        <FormAlert>{error}</FormAlert>
      </div>
    </Panel>
  )
}

function Appointments({ items, editable, onCancelled }: { items: Appointment[]; editable: boolean; onCancelled: (a: Appointment) => void }) {
  const [error, setError] = useState<string>()
  const cancel = async (a: Appointment) => {
    try {
      await cancelAppointment(a.id)
      onCancelled(a)
    } catch (err) {
      setError(message(err, 'The appointment wasn’t cancelled. Try again.'))
    }
  }
  return (
    <Panel title="Upcoming appointments">
      <FormAlert>{error}</FormAlert>
      {items.length === 0 ? (
        <p>No upcoming appointments.</p>
      ) : (
        <ul aria-label="Appointments">
          {items.map((a) => (
            <li key={a.id}>
              {new Date(a.startsAt).toLocaleString()} · {a.donorName} ({a.donorId}){' '}
              {editable && (
                <button type="button" className={formStyles.more} onClick={() => cancel(a)} aria-label={`Cancel appointment for ${a.donorName}`}>
                  Cancel
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
