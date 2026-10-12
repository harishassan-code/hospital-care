import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  getCapabilities,
  getHospital,
  typeLabel,
  type Department,
  type HospitalDetail,
  type LocationItem,
  type WardItem,
} from '../../api/hospitals'
import { Panel } from '../../components/ui/Panel'
import { ActiveBadge } from '../../features/hospitals/ActiveBadge'
import styles from '../../features/hospitals/Hospitals.module.css'
import { StructureSection } from '../../features/hospitals/StructureSection'
import { canEdit } from '../../features/staff/roles'
import { useStaff } from '../../features/staff/staffContext'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

export default function HospitalDetailPage() {
  const { id } = useParams()
  return <HospitalDetailView key={id} hospitalId={Number(id)} />
}

function HospitalDetailView({ hospitalId }: { hospitalId: number }) {
  const { role } = useStaff()
  const editable = canEdit(role, 'hospitals')
  const { result, setData } = useLoad(useCallback(() => Promise.all([getHospital(hospitalId), getCapabilities()]), [hospitalId]))

  if (result.state === 'failed' && result.status === 404) {
    return (
      <div className={pageStyles.stack}>
        <p role="status">No hospital with that id.</p>
        <Link to="/staff/hospitals" className={styles.back}>
          ← All hospitals
        </Link>
      </div>
    )
  }
  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />

  const [hospital, capabilities] = result.data
  const update = (change: (h: HospitalDetail) => HospitalDetail) => setData(([h, c]) => [change(h), c])
  const capabilityNames = capabilities.filter((c) => hospital.capabilities.includes(c.code)).map((c) => c.name)
  const departmentName = (id: number | null) => hospital.departments.find((d) => d.id === id)?.name

  return (
    <div className={pageStyles.stack}>
      <Link to="/staff/hospitals" className={styles.back}>
        ← All hospitals
      </Link>
      <Panel
        title={hospital.name}
        id="hospital"
        aside={
          editable && (
            <Link to={`/staff/hospitals/${hospital.id}/edit`} className={styles.action}>
              Edit details
            </Link>
          )
        }
      >
        <div className={styles.meta}>
          <p className={styles.rowControls}>
            <strong>{typeLabel(hospital.type)}</strong>
            <ActiveBadge active={hospital.isActive} />
          </p>
          <p>{hospital.address}</p>
          {hospital.phone && <p>Phone: {hospital.phone}</p>}
          <p>
            Coordinates: {hospital.latitude}, {hospital.longitude}
          </p>
        </div>
      </Panel>

      <Panel title="Capabilities" id="capabilities">
        {capabilityNames.length === 0 ? (
          <p>No capabilities recorded.</p>
        ) : (
          <ul className={styles.chips} aria-label="Capabilities">
            {capabilityNames.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        )}
      </Panel>

      <StructureSection<Department>
        hospitalId={hospital.id}
        kind="departments"
        title="Departments"
        noun="department"
        items={hospital.departments}
        describe={(d) => d.name}
        fields={[{ key: 'name', label: 'Department name' }]}
        editable={editable}
        onAdded={(d) => update((h) => ({ ...h, departments: [...h.departments, d] }))}
        onRemoved={(id) =>
          update((h) => ({
            ...h,
            departments: h.departments.filter((d) => d.id !== id),
            wards: h.wards.map((w) => (w.departmentId === id ? { ...w, departmentId: null } : w)),
          }))
        }
      />

      <StructureSection<WardItem>
        hospitalId={hospital.id}
        kind="wards"
        title="Wards"
        noun="ward"
        items={hospital.wards}
        describe={(w) =>
          [w.name, w.kind, departmentName(w.departmentId), `${w.bedCount} ${w.bedCount === 1 ? 'bed' : 'beds'}`]
            .filter(Boolean)
            .join(' · ')
        }
        fields={[
          { key: 'name', label: 'Ward name' },
          { key: 'kind', label: 'Kind of care' },
          {
            key: 'departmentId',
            label: 'Department',
            options: [{ value: '', label: 'No department' }, ...hospital.departments.map((d) => ({ value: String(d.id), label: d.name }))],
          },
        ]}
        editable={editable}
        onAdded={(w) => update((h) => ({ ...h, wards: [...h.wards, w] }))}
        onRemoved={(id) => update((h) => ({ ...h, wards: h.wards.filter((w) => w.id !== id) }))}
      />

      <StructureSection<LocationItem>
        hospitalId={hospital.id}
        kind="locations"
        title="Storage locations"
        noun="location"
        items={hospital.locations}
        describe={(l) => l.name}
        fields={[{ key: 'name', label: 'Location name' }]}
        editable={editable}
        onAdded={(l) => update((h) => ({ ...h, locations: [...h.locations, l] }))}
        onRemoved={(id) => update((h) => ({ ...h, locations: h.locations.filter((l) => l.id !== id) }))}
      />
    </div>
  )
}
