import { Panel } from '../../components/ui/Panel'
import { dayOfStay, dischargesToday } from '../beds/beds'
import { useStaff, type StaffData } from '../staff/staffContext'
import styles from './Overview.module.css'

/** Beds expected to free up today: what bed managers plan admissions around. */
export function DischargesToday({ data }: { data: StaffData }) {
  const { now } = useStaff()
  const wardName = new Map(data.wards.map((w) => [w.id, w.name]))
  const beds = dischargesToday(data.beds, now)

  return (
    <Panel title="Expected discharges today" aside={<span className={styles.count}>{beds.length} beds</span>}>
      {beds.length === 0 ? (
        <p>No discharges are planned for today.</p>
      ) : (
        <div className="table-scroll">
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Bed</th>
                <th scope="col">Ward</th>
                <th scope="col">Patient</th>
                <th scope="col">Day of stay</th>
              </tr>
            </thead>
            <tbody>
              {beds.map((bed) => (
                <tr key={bed.id}>
                  <td className={styles.mono}>{bed.label}</td>
                  <td>{wardName.get(bed.ward)}</td>
                  <td>{bed.patient && `${bed.patient.initials} · ${bed.patient.age} ${bed.patient.sex}`}</td>
                  <td className={styles.mono}>{dayOfStay(bed, now)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}
