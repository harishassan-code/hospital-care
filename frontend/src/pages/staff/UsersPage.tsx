import { useCallback, useState } from 'react'
import { ApiError, fieldErrors } from '../../api/client'
import { getHospitals, type Hospital } from '../../api/hospitals'
import { getUsers, HOSPITAL_ROLES, updateUserRole, type AccountRole, type UserSummary } from '../../api/users'
import { FormAlert } from '../../components/form/FormAlert'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import styles from '../../features/hospitals/Hospitals.module.css'
import { ROLES } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

const ACCOUNT_ROLES: readonly { id: AccountRole; label: string }[] = [...ROLES, { id: 'patient', label: 'Patient' }]
const roleLabel = (role: AccountRole) => ACCOUNT_ROLES.find((r) => r.id === role)?.label ?? role

function saveError(error: unknown): string {
  const status = error instanceof ApiError ? error.status : 0
  if (status === 403) return 'Your role can’t change other people’s roles.'
  const errors = fieldErrors(error)
  if (status === 400 && (errors.role || errors.hospitalId || errors.detail)) return errors.role ?? errors.hospitalId ?? errors.detail
  return 'The hospital’s system didn’t respond, so the role wasn’t changed. Try again.'
}

const NEEDS_HOSPITAL = 'Choose the hospital this person works at.'

/** Admin only: every account with its role and hospital, and a way to change both. */
export default function UsersPage() {
  const { result, setData } = useLoad(getUsers)
  const loadHospitals = useCallback(() => getHospitals().then((all) => all.filter((h) => h.isActive)), [])
  const hospitals = useLoad(loadHospitals).result
  const [status, setStatus] = useState('')
  const [alert, setAlert] = useState('')

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const saved = (user: UserSummary) => {
    setData((users) => users.map((u) => (u.id === user.id ? user : u)))
    setAlert('')
    const where = user.hospital ? ` at ${user.hospital.name}` : ''
    setStatus(`${user.fullName} is now ${roleLabel(user.role)}${where}. The change applies on their next page load.`)
  }
  const failed = (message: string) => {
    setStatus('')
    setAlert(message)
  }

  return (
    <div className={pageStyles.stack}>
      <Panel title="Users and roles" aside={<span className={pageStyles.note}>{result.data.length} accounts</span>}>
        <p className={pageStyles.note}>
          A role decides which pages and actions someone has; doctors, nurses, blood bank and pharmacists also need the
          hospital they work at. To add a staff member, they sign up, then you give them a role and a hospital here.
        </p>
        <p role="status" aria-live="polite">
          {status}
        </p>
        <FormAlert>{alert || undefined}</FormAlert>
        <div className="table-scroll">
          <table className={styles.table}>
            <caption className="visually-hidden">Users and their roles</caption>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Email</th>
                <th scope="col">Hospital</th>
                <th scope="col">Role</th>
              </tr>
            </thead>
            <tbody>
              {result.data.map((user) => (
                <UserRow
                  key={user.id}
                  user={user}
                  hospitals={hospitals.state === 'ready' ? hospitals.data : []}
                  onSaved={saved}
                  onFailed={failed}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

type UserRowProps = {
  user: UserSummary
  hospitals: readonly Hospital[]
  onSaved: (user: UserSummary) => void
  onFailed: (message: string) => void
}

function UserRow({ user, hospitals, onSaved, onFailed }: UserRowProps) {
  const me = useStaff().user
  const [role, setRole] = useState(user.role)
  const [hospitalId, setHospitalId] = useState<number | null>(user.hospital?.id ?? null)
  const [pending, setPending] = useState(false)
  const selectId = `role-${user.id}`
  const hospitalSelectId = `hospital-${user.id}`
  const hospitalChanged = hospitalId !== (user.hospital?.id ?? null)
  // The user's current hospital stays choosable even if it has since been made inactive.
  const choices = user.hospital && !hospitals.some((h) => h.id === user.hospital?.id) ? [user.hospital, ...hospitals] : hospitals

  async function save() {
    if (HOSPITAL_ROLES.includes(role) && hospitalId === null) {
      onFailed(`${NEEDS_HOSPITAL} ${roleLabel(role)} accounts work at one hospital.`)
      return
    }
    setPending(true)
    try {
      onSaved(await updateUserRole(user.id, role, hospitalChanged ? hospitalId : undefined))
    } catch (error) {
      setRole(user.role)
      setHospitalId(user.hospital?.id ?? null)
      onFailed(saveError(error))
    } finally {
      setPending(false)
    }
  }

  return (
    <tr>
      <td>
        {user.fullName}
        {!user.isActive && (
          <>
            {' '}
            <StatusBadge tone="neutral">Deactivated</StatusBadge>
          </>
        )}
      </td>
      <td>{user.email}</td>
      <td>
        {user.roleLocked ? (
          (user.hospital?.name ?? (user.role === 'admin' ? 'All hospitals' : 'No hospital'))
        ) : (
          <>
            <label className="visually-hidden" htmlFor={hospitalSelectId}>
              Hospital for {user.fullName}
            </label>
            <select
              id={hospitalSelectId}
              className={styles.select}
              value={hospitalId ?? ''}
              onChange={(e) => setHospitalId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">{role === 'admin' ? 'All hospitals' : 'No hospital'}</option>
              {choices.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
            </select>
          </>
        )}
      </td>
      <td>
        {user.roleLocked ? (
          <span>
            {roleLabel(user.role)}{' '}
            <span className={pageStyles.note}>{user.id === me.id ? '(your account)' : '(superuser: change in Django admin)'}</span>
          </span>
        ) : (
          <div className={styles.rowControls}>
            <label className="visually-hidden" htmlFor={selectId}>
              Role for {user.fullName}
            </label>
            <select
              id={selectId}
              className={styles.select}
              value={role}
              onChange={(e) => setRole(e.target.value as AccountRole)}
            >
              {ACCOUNT_ROLES.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              className={styles.action}
              disabled={pending || (role === user.role && !hospitalChanged)}
              aria-label={`${pending ? 'Saving' : 'Save'} role for ${user.fullName}`}
              onClick={save}
            >
              {pending ? 'Saving…' : 'Save'}
            </button>
          </div>
        )}
      </td>
    </tr>
  )
}
