import { Ambulance, Building2, Clock, Siren } from 'lucide-react'
import { Link } from 'react-router-dom'
import { BED_LEVEL_LABEL, BLOOD_LEVEL_LABEL, type NetworkSnapshot as Snapshot } from '../../api/public'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatClock } from '../../lib/time'
import { TYPE_LABEL } from '../beds/beds'
import { BED_TONE, BLOOD_TONE } from './network'
import styles from './Network.module.css'

/** The city at a glance (B19): departments, the shortest wait, ambulances, and beds and blood as levels. */
export function NetworkSnapshot({ snapshot }: { snapshot: Snapshot }) {
  const { emergency, ambulances } = snapshot
  const reported = emergency.accepting + emergency.busy + emergency.diverting
  return (
    <div className={styles.snapshot}>
      <ul className={styles.stats} aria-label="The network right now">
        <li className={styles.stat}>
          <Building2 className={styles.statIcon} aria-hidden="true" />
          <span className={styles.statValue}>{snapshot.hospitals}</span>
          <span className={styles.statLabel}>hospitals in the network</span>
        </li>
        <li className={styles.stat}>
          <Siren className={styles.statIcon} aria-hidden="true" />
          <span className={styles.statValue}>
            {emergency.accepting}
            <span className={styles.statOf}> of {reported}</span>
          </span>
          <span className={styles.statLabel}>emergency departments accepting patients</span>
          {(emergency.busy > 0 || emergency.diverting > 0) && (
            <span className={styles.statNote}>
              {[
                emergency.busy > 0 && `${emergency.busy} very busy`,
                emergency.diverting > 0 && `${emergency.diverting} not accepting ambulances`,
              ]
                .filter(Boolean)
                .join(' · ')}
            </span>
          )}
        </li>
        <li className={styles.stat}>
          <Clock className={styles.statIcon} aria-hidden="true" />
          {emergency.shortestWait ? (
            <>
              <span className={styles.statValue}>
                {emergency.shortestWait.waitMinutes}
                <span className={styles.statOf}> min</span>
              </span>
              <span className={styles.statLabel}>
                shortest emergency wait, at{' '}
                <Link to={`/hospitals/${emergency.shortestWait.hospitalId}`}>{emergency.shortestWait.name}</Link>
              </span>
            </>
          ) : (
            <>
              <span className={styles.statValue}>–</span>
              <span className={styles.statLabel}>no emergency waits reported</span>
            </>
          )}
        </li>
        <li className={styles.stat}>
          <Ambulance className={styles.statIcon} aria-hidden="true" />
          <span className={styles.statValue}>
            {ambulances.available}
            <span className={styles.statOf}> of {ambulances.total}</span>
          </span>
          <span className={styles.statLabel}>ambulances free to respond</span>
        </li>
      </ul>

      <div className={styles.levels}>
        <section className={styles.levelGroup} aria-labelledby="beds-levels">
          <h3 id="beds-levels" className={styles.levelTitle}>
            Beds across the city
          </h3>
          {snapshot.beds.length === 0 ? (
            <p className={styles.muted}>No beds reported yet.</p>
          ) : (
            <ul className={styles.levelList}>
              {snapshot.beds.map((b) => (
                <li key={b.bedType}>
                  <span>{TYPE_LABEL[b.bedType]}</span>
                  <StatusBadge tone={BED_TONE[b.level]}>{BED_LEVEL_LABEL[b.level]}</StatusBadge>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className={styles.levelGroup} aria-labelledby="blood-levels">
          <h3 id="blood-levels" className={styles.levelTitle}>
            Blood supply
          </h3>
          {snapshot.blood.length === 0 ? (
            <p className={styles.muted}>No blood stock reported yet.</p>
          ) : (
            <ul className={`${styles.levelList} ${styles.bloodList}`}>
              {snapshot.blood.map((b) => (
                <li key={b.group}>
                  <span className={styles.group}>{b.group}</span>
                  <StatusBadge tone={BLOOD_TONE[b.level]}>{BLOOD_LEVEL_LABEL[b.level]}</StatusBadge>
                </li>
              ))}
            </ul>
          )}
          <p className={styles.muted}>Red cells, against the minimum the network’s blood banks keep.</p>
        </section>
      </div>
      <p className={styles.updated}>Updated {formatClock(new Date(snapshot.updatedAt))}. Availability is shown as levels, not exact counts.</p>
    </div>
  )
}
