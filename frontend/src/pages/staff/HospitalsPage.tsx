import { useState } from 'react'
import { Link } from 'react-router-dom'
import { getHospitals, HOSPITAL_TYPES, typeLabel, type Hospital, type HospitalType } from '../../api/hospitals'
import { FilterBar } from '../../components/ui/FilterBar'
import { Panel } from '../../components/ui/Panel'
import { ActiveBadge } from '../../features/hospitals/ActiveBadge'
import styles from '../../features/hospitals/Hospitals.module.css'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

type TypeFilter = 'all' | HospitalType

function matches(hospital: Hospital, type: TypeFilter, query: string): boolean {
  const q = query.trim().toLowerCase()
  return (type === 'all' || hospital.type === type) && (!q || `${hospital.name} ${hospital.address}`.toLowerCase().includes(q))
}

export default function HospitalsPage() {
  const { role } = useStaff()
  const { result } = useLoad(getHospitals)
  const [type, setType] = useState<TypeFilter>('all')
  const [query, setQuery] = useState('')

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const hospitals = result.data
  const shown = hospitals.filter((h) => matches(h, type, query))
  const options = [{ value: 'all' as const, label: 'All' }, ...HOSPITAL_TYPES].map((option) => ({
    ...option,
    count: hospitals.filter((h) => matches(h, option.value, '')).length,
  }))

  return (
    <div className={pageStyles.stack}>
      <Panel
        title="Hospital network"
        aside={
          canEdit(role, 'hospitals') && (
            <Link to="/staff/hospitals/new" className={`${styles.action} ${styles.primary}`}>
              Register a hospital
            </Link>
          )
        }
      >
        <div className={pageStyles.toolbar}>
          <label className={styles.search}>
            Search hospitals
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Name or address" />
          </label>
          <FilterBar label="Show" options={options} value={type} onChange={setType} />
        </div>
        {hospitals.length === 0 ? (
          <p>No hospitals registered yet.</p>
        ) : shown.length === 0 ? (
          <p>No hospitals match. Clear the search or choose another type.</p>
        ) : (
          <div className="table-scroll">
            <table className={styles.table}>
              <caption className="visually-hidden">Hospitals in the network</caption>
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Type</th>
                  <th scope="col">Address</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((h) => (
                  <tr key={h.id}>
                    <td>
                      <Link to={`/staff/hospitals/${h.id}`}>{h.name}</Link>
                    </td>
                    <td>{typeLabel(h.type)}</td>
                    <td>{h.address}</td>
                    <td>
                      <ActiveBadge active={h.isActive} />
                    </td>
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
