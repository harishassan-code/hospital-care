import { useCallback } from 'react'
import { getDonor, type Donor } from '../../api/donors'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { useLoad } from '../../lib/useLoad'
import { COMPONENT_LABEL, formatGroup, UNIT_STATUS_LABEL } from '../blood/blood'
import { AppointmentsSection } from './AppointmentsSection'
import { DonorSection } from './DonorSection'
import styles from './Donors.module.css'
import { eligibilityLabel, lastDonationLabel } from './donors'
import { ScreeningForm } from './ScreeningForm'

type Props = {
  code: string
  canWrite: boolean
  /** The server's answer after a change, so the list row can match. */
  onChanged: (donor: Donor) => void
  onClose: () => void
}

/** One donor: details, eligibility, units, screening and appointments. Opened from the list, kept in ?donor=. */
export function DonorPanel({ code, canWrite, onChanged, onClose }: Props) {
  const load = useCallback(() => getDonor(code), [code])
  const { result, setData } = useLoad(load)

  if (result.state === 'loading') {
    return (
      <Panel title="Donor">
        <p role="status">Loading donor…</p>
      </Panel>
    )
  }
  if (result.state === 'failed') {
    return (
      <Panel title="Donor" aside={<button type="button" className={styles.back} onClick={onClose}>Close</button>}>
        <p role="alert">Couldn’t load this donor. Close it and open the donor again.</p>
      </Panel>
    )
  }

  const donor = result.data
  const saved = (next: Donor) => {
    setData((current) => ({ ...current, ...next }))
    onChanged(next)
  }

  return (
    <Panel title={`Donor ${donor.id}`} aside={<button type="button" className={styles.back} onClick={onClose}>Close</button>}>
      <dl className={styles.facts}>
        <div>
          <dt>Name</dt>
          <dd>{donor.fullName}</dd>
        </div>
        <div>
          <dt>Blood group</dt>
          <dd>{formatGroup(donor.bloodGroup)}</dd>
        </div>
        <div>
          <dt>Phone</dt>
          <dd>{donor.phone || 'Not given'}</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{donor.email || 'Not given'}</dd>
        </div>
        <div>
          <dt>Last donation</dt>
          <dd>{lastDonationLabel(donor.lastDonationAt)}</dd>
        </div>
        <div>
          <dt>Eligibility</dt>
          <dd>
            <StatusBadge tone={donor.eligible ? 'ok' : donor.eligibleFrom ? 'warning' : 'critical'}>
              {eligibilityLabel(donor)}
            </StatusBadge>
          </dd>
        </div>
      </dl>
      {!donor.eligible && donor.ineligibleReason && (
        <p>
          <strong>Reason:</strong> {donor.ineligibleReason}
        </p>
      )}

      <DonorSection title="Units from this donor">
        {donor.units.length === 0 ? (
          <p className={styles.note}>No units from this donor.</p>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table} aria-label="Units from this donor">
              <thead>
                <tr>
                  <th scope="col">Unit ID</th>
                  <th scope="col">Component</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {donor.units.map((unit) => (
                  <tr key={unit.id}>
                    <td className={styles.mono}>{unit.id}</td>
                    <td>{COMPONENT_LABEL[unit.component]}</td>
                    <td>{UNIT_STATUS_LABEL[unit.status]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DonorSection>

      {canWrite && (
        <DonorSection title="Screening">
          <ScreeningForm donor={donor} onSaved={saved} />
        </DonorSection>
      )}

      <AppointmentsSection donor={donor} canWrite={canWrite} />
    </Panel>
  )
}
