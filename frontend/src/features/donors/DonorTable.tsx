import type { Donor } from '../../api/donors'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatGroup } from '../blood/blood'
import styles from './Donors.module.css'
import { eligibilityLabel, lastDonationLabel } from './donors'

type Props = {
  donors: Donor[]
  selectedId: string | null
  onSelect: (code: string) => void
}

/** Donors as a table. Phone and email stay out of it: the donor panel shows them. */
export function DonorTable({ donors, selectedId, onSelect }: Props) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table} aria-label="Donors">
        <thead>
          <tr>
            <th scope="col">Code</th>
            <th scope="col">Name</th>
            <th scope="col">Blood group</th>
            <th scope="col">Last donation</th>
            <th scope="col">Eligibility</th>
          </tr>
        </thead>
        <tbody>
          {donors.map((donor) => (
            <tr key={donor.id} aria-selected={donor.id === selectedId ? 'true' : undefined}>
              <td className={styles.mono}>{donor.id}</td>
              <td>
                <button
                  type="button"
                  className={styles.nameButton}
                  aria-current={donor.id === selectedId ? 'true' : undefined}
                  onClick={() => onSelect(donor.id)}
                >
                  {donor.fullName}
                </button>
              </td>
              <td className={styles.mono}>{formatGroup(donor.bloodGroup)}</td>
              <td>{lastDonationLabel(donor.lastDonationAt)}</td>
              <td>
                <StatusBadge tone={donor.eligible ? 'ok' : donor.eligibleFrom ? 'warning' : 'critical'}>
                  {eligibilityLabel(donor)}
                </StatusBadge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
