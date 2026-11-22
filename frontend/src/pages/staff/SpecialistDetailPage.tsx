import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, fieldErrors } from '../../api/client'
import { getSpecialist, removeOnCallWindow, type OnCallWindow } from '../../api/specialists'
import { FormAlert } from '../../components/form/FormAlert'
import { Panel } from '../../components/ui/Panel'
import { ActiveBadge } from '../../features/hospitals/ActiveBadge'
import hospitalStyles from '../../features/hospitals/Hospitals.module.css'
import { OnCallForm } from '../../features/specialists/OnCallForm'
import { hasStarted } from '../../features/specialists/rules'
import { karachiDateTime, onCallText } from '../../features/specialists/schedule'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

/** One specialist: the profile, the on-call times still ahead, and (for admins and nurses) adding and removing them. */
export default function SpecialistDetailPage() {
  const { id } = useParams()
  return <SpecialistDetailView key={id} specialistId={Number(id)} />
}

function SpecialistDetailView({ specialistId }: { specialistId: number }) {
  const { role, now } = useStaff()
  const editable = canEdit(role, 'specialists')
  const { result, setData } = useLoad(useCallback(() => getSpecialist(specialistId), [specialistId]))
  const [status, setStatus] = useState('')
  const [alert, setAlert] = useState<string>()

  if (result.state === 'failed' && result.status === 404) {
    return (
      <div className={pageStyles.stack}>
        <p role="status">No specialist with that id.</p>
        <Link to="/staff/specialists" className={hospitalStyles.back}>
          ← All specialists
        </Link>
      </div>
    )
  }
  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const specialist = result.data

  /** Reload the profile, so the times and the on-call line match the server after a change. */
  const refresh = () =>
    getSpecialist(specialistId)
      .then((fresh) => setData(() => fresh))
      .catch(() => undefined) // the page keeps what it showed; the next visit reloads it

  async function remove(window: OnCallWindow) {
    setAlert(undefined)
    setStatus('')
    try {
      await removeOnCallWindow(specialist.id, window.id)
      setStatus(`Removed the on-call time from ${karachiDateTime(window.startsAt)}.`)
    } catch (error) {
      setAlert(removeFailure(error))
    }
    await refresh()
  }

  return (
    <div className={pageStyles.stack}>
      <Link to="/staff/specialists" className={hospitalStyles.back}>
        ← All specialists
      </Link>
      <Panel
        title={specialist.name}
        id="specialist"
        aside={
          editable && (
            <Link to={`/staff/specialists/${specialist.id}/edit`} className={hospitalStyles.action}>
              Edit details
            </Link>
          )
        }
      >
        <div className={hospitalStyles.meta}>
          <p className={hospitalStyles.rowControls}>
            <strong>{specialist.specialty}</strong>
            <ActiveBadge active={specialist.isActive} />
          </p>
          <p>{specialist.hospital.name}</p>
          <p>{onCallText(specialist, now)}</p>
        </div>
      </Panel>

      <Panel title="On-call times" id="on-call">
        {specialist.onCall.length === 0 ? (
          <p>No on-call times ahead.</p>
        ) : (
          <div className="table-scroll">
            <table className={hospitalStyles.table} aria-label="Upcoming on-call times">
              <thead>
                <tr>
                  <th scope="col">Starts</th>
                  <th scope="col">Ends</th>
                  {editable && <th scope="col">Remove</th>}
                </tr>
              </thead>
              <tbody>
                {specialist.onCall.map((window) => (
                  <tr key={window.id}>
                    <td>{karachiDateTime(window.startsAt)}</td>
                    <td>{karachiDateTime(window.endsAt)}</td>
                    {editable && (
                      <td>
                        {!hasStarted(window, now) && (
                          <button
                            type="button"
                            className={hospitalStyles.action}
                            aria-label={`Remove the on-call time from ${karachiDateTime(window.startsAt)}`}
                            onClick={() => remove(window)}
                          >
                            Remove
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p role="status" aria-live="polite">
          {status}
        </p>
        <FormAlert>{alert}</FormAlert>
        {editable && (
          <OnCallForm
            specialistId={specialist.id}
            onAdded={(window) => {
              setStatus(`Added on-call from ${karachiDateTime(window.startsAt)} to ${karachiDateTime(window.endsAt)}.`)
              void refresh()
            }}
          />
        )}
      </Panel>
    </div>
  )
}

/** Why a window wasn't removed: the server's words for a started window, or a plain reason for the rest. */
function removeFailure(error: unknown): string {
  const status = error instanceof ApiError ? error.status : 0
  if (status === 409) return fieldErrors(error).detail ?? 'That window has started, so it stays as history.'
  if (status === 403) return 'Your role can’t change on-call times.'
  return 'The hospital’s system didn’t respond, so the window wasn’t removed. Try again.'
}
