import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { getHospitals } from '../../api/hospitals'
import { getSpecialists } from '../../api/specialists'
import { Checkbox } from '../../components/form/Checkbox'
import { Field } from '../../components/form/Field'
import { Panel } from '../../components/ui/Panel'
import { ActiveBadge } from '../../features/hospitals/ActiveBadge'
import hospitalStyles from '../../features/hospitals/Hospitals.module.css'
import { onCallText } from '../../features/specialists/schedule'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

const ALL = 'all'

/**
 * The specialists in the network and who is on call now (stories #61 and #62). "Available now" asks the server for
 * the ones on call. The hospital and specialty filters narrow the loaded list in the browser.
 */
export default function SpecialistsPage() {
  const { role, now } = useStaff()
  const [availableNow, setAvailableNow] = useState(false)
  const [hospital, setHospital] = useState(ALL)
  const [specialty, setSpecialty] = useState(ALL)
  const load = useCallback(() => Promise.all([getSpecialists({ availableNow }), getHospitals()]), [availableNow])
  const { result } = useLoad(load)

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const [specialists, hospitals] = result.data
  const specialties = [...new Set(specialists.map((s) => s.specialty))].sort((a, b) => a.localeCompare(b))
  // A specialty that the "Available now" filter has hidden goes back to "All", so the list never shows a stale choice.
  const specialtyChoice = specialties.includes(specialty) ? specialty : ALL
  const shown = specialists.filter(
    (s) =>
      (hospital === ALL || String(s.hospital.id) === hospital) &&
      (specialtyChoice === ALL || s.specialty === specialtyChoice),
  )

  return (
    <div className={pageStyles.stack}>
      <Panel
        title="Specialists"
        aside={
          canEdit(role, 'specialists') && (
            <Link to="/staff/specialists/new" className={`${hospitalStyles.action} ${hospitalStyles.primary}`}>
              Add specialist
            </Link>
          )
        }
      >
        <div className={pageStyles.toolbar}>
          <Field id="hospital-filter" label="Hospital">
            <select
              id="hospital-filter"
              className={hospitalStyles.select}
              value={hospital}
              onChange={(e) => setHospital(e.target.value)}
            >
              <option value={ALL}>All hospitals</option>
              {hospitals.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
            </select>
          </Field>
          <Field id="specialty-filter" label="Specialty">
            <select
              id="specialty-filter"
              className={hospitalStyles.select}
              value={specialtyChoice}
              onChange={(e) => setSpecialty(e.target.value)}
            >
              <option value={ALL}>All specialties</option>
              {specialties.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Checkbox id="available-now" checked={availableNow} onChange={setAvailableNow}>
            Available now
          </Checkbox>
        </div>
        {specialists.length === 0 ? (
          <p>{availableNow ? 'Nobody is on call right now.' : 'No specialists listed yet.'}</p>
        ) : shown.length === 0 ? (
          <p>No specialists match. Clear the filters or turn off Available now.</p>
        ) : (
          <div className="table-scroll">
            <table className={hospitalStyles.table} aria-label="Specialists">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Specialty</th>
                  <th scope="col">Hospital</th>
                  <th scope="col">Status</th>
                  <th scope="col">On call</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((s) => (
                  <tr key={s.id}>
                    <th scope="row">
                      <Link to={`/staff/specialists/${s.id}`}>{s.name}</Link>
                    </th>
                    <td>{s.specialty}</td>
                    <td>{s.hospital.name}</td>
                    <td>
                      <ActiveBadge active={s.isActive} />
                    </td>
                    <td>{onCallText(s, now)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}
