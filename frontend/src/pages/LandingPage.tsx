import { useEffect, useState } from 'react'
import { getPublicStatus, type PublicStatus } from '../api/publicStatus'
import { SiteFooter } from '../components/layout/SiteFooter'
import { SiteHeader } from '../components/layout/SiteHeader'
import { hospital } from '../config/hospital'
import { formatClock } from '../lib/time'
import { useNow } from '../lib/useNow'
import { useScrollToHash } from '../lib/useScrollToHash'
import { Destination } from '../features/landing/Destination'
import { DoctorSchedule } from '../features/landing/DoctorSchedule'
import { EmergencyStatus } from '../features/landing/EmergencyStatus'
import { RailRow } from '../features/landing/FloorLines'
import { ALL_LINES } from '../features/landing/lines'
import { SignInOptions } from '../features/landing/SignInOptions'
import { WayfindingSign } from '../features/landing/WayfindingSign'
import styles from './LandingPage.module.css'

export default function LandingPage() {
  const now = useNow()
  const [status, setStatus] = useState<PublicStatus | null>(null)
  const [failed, setFailed] = useState(false)
  useScrollToHash(status !== null || failed)

  useEffect(() => {
    let active = true
    getPublicStatus()
      .then((s) => active && setStatus(s))
      .catch(() => active && setFailed(true))
    return () => {
      active = false
    }
  }, [])

  return (
    <div className={styles.page}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <SiteHeader />

      <main id="main" className={styles.main}>
        <div className={styles.container}>
          <RailRow lines={{}} className={styles.heroHead}>
            <h1 className={styles.title}>Where do you need to go?</h1>
          </RailRow>

          <WayfindingSign status={status} failed={failed} now={now} />

          <RailRow lines={{ through: ALL_LINES }} className={styles.note}>
            <p>
              {status && <span className={styles.updated}>Updated {formatClock(new Date(status.updatedAt))} · </span>}
              Times are estimates. If it’s life-threatening, call{' '}
              <a href={`tel:${hospital.emergencyNumber}`}>{hospital.emergencyNumber}</a>.
            </p>
          </RailRow>

          <Destination index={0} lede="Open 24 hours, every day. The most serious cases are always seen first.">
            <EmergencyStatus status={status} failed={failed} />
          </Destination>

          <Destination index={1} lede="Who is on duty today, by department. Shifts that run overnight continue past midnight.">
            {status ? (
              <DoctorSchedule doctors={status.doctors} now={now} />
            ) : (
              <p>{failed ? 'Today’s schedule isn’t available right now.' : 'Loading today’s schedule…'}</p>
            )}
          </Destination>

          <Destination index={2} lede="One sign-in for patients and hospital staff.">
            <SignInOptions />
          </Destination>
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}
