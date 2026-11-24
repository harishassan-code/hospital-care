import { ArrowLeft, Droplet, ExternalLink, MapPin, Phone } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { BED_LEVEL_LABEL, ER_STATUS_LABEL, getPublicHospital, type PublicHospitalDetail } from '../api/public'
import { SiteFooter } from '../components/layout/SiteFooter'
import { SiteHeader } from '../components/layout/SiteHeader'
import { StatusBadge } from '../components/ui/StatusBadge'
import { hospital as site } from '../config/hospital'
import { TYPE_LABEL } from '../features/beds/beds'
import { BED_TONE, ER_TONE, mapLink, PUBLIC_REFRESH_MS } from '../features/network/network'
import { formatClock } from '../lib/time'
import styles from './HospitalPublicPage.module.css'

type State = { hospital: PublicHospitalDetail | null; failed: boolean; notFound: boolean }

/**
 * One member hospital's public page (B19): its emergency department, services, departments, who is on duty and its
 * beds as levels. Doctors' names appear only for signed-in hospital staff (#122).
 */
export default function HospitalPublicPage() {
  const { id = '' } = useParams()
  // A fresh page per hospital, so nothing from the last one shows while the next loads.
  return <HospitalPage key={id} id={id} />
}

function HospitalPage({ id }: { id: string }) {
  const [state, setState] = useState<State>({ hospital: null, failed: false, notFound: false })

  useEffect(() => {
    let active = true
    const load = () =>
      getPublicHospital(id)
        .then((hospital) => active && setState({ hospital, failed: false, notFound: false }))
        .catch((error) => {
          if (!active) return
          const notFound = error instanceof ApiError && error.status === 404
          setState((s) => ({ hospital: notFound ? null : s.hospital, failed: !notFound, notFound }))
        })
    void load()
    const timer = setInterval(() => {
      if (document.visibilityState !== 'hidden') void load()
    }, PUBLIC_REFRESH_MS)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [id])

  const { hospital } = state
  useEffect(() => {
    document.title = hospital ? `${hospital.name} · ${site.name}` : site.name
    return () => {
      document.title = site.name
    }
  }, [hospital])

  return (
    <div className={styles.page}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <SiteHeader />
      <main id="main" className={styles.main}>
        <Link to="/#hospitals" className={styles.back}>
          <ArrowLeft aria-hidden="true" size={18} /> All hospitals
        </Link>
        {hospital ? (
          <Profile hospital={hospital} />
        ) : state.notFound ? (
          <div className={styles.notFound}>
            <h1>We couldn’t find that hospital</h1>
            <p>It may have left the network. Choose another from the list.</p>
          </div>
        ) : (
          <p className={styles.state}>{state.failed ? 'This hospital’s page isn’t available right now.' : 'Loading…'}</p>
        )}
      </main>
      <SiteFooter />
    </div>
  )
}

function Profile({ hospital }: { hospital: PublicHospitalDetail }) {
  const er = hospital.emergency
  return (
    <article className={styles.profile} aria-labelledby="hospital-name">
      <header className={styles.head}>
        <p className={styles.eyebrow}>
          {hospital.type === 'bloodBank' ? (
            <>
              <Droplet aria-hidden="true" size={15} /> Blood bank in the {site.name} network
            </>
          ) : (
            <>Member of the {site.name} network</>
          )}
        </p>
        <h1 id="hospital-name" className={styles.name}>
          {hospital.name}
        </h1>
        <ul className={styles.contact}>
          <li>
            <MapPin aria-hidden="true" size={16} />
            {hospital.address}
            <a href={mapLink(hospital)} target="_blank" rel="noreferrer" className={styles.mapLink}>
              Map <ExternalLink aria-hidden="true" size={14} />
              <span className="visually-hidden"> (opens in a new tab)</span>
            </a>
          </li>
          {hospital.phone && (
            <li>
              <Phone aria-hidden="true" size={16} />
              <a href={`tel:${hospital.phone.replace(/[^\d+]/g, '')}`}>{hospital.phone}</a>
            </li>
          )}
        </ul>
      </header>

      {hospital.type !== 'bloodBank' && (
        <section className={`${styles.card} ${styles.er}`} aria-labelledby="er-title">
          <h2 id="er-title">Emergency department</h2>
          {er ? (
            <>
              <StatusBadge tone={ER_TONE[er.status]}>{ER_STATUS_LABEL[er.status]}</StatusBadge>
              <dl className={styles.erFigures}>
                <div>
                  <dt>Estimated wait</dt>
                  <dd>
                    {er.waitMinutes}
                    <span> min</span>
                  </dd>
                </div>
                <div>
                  <dt>Waiting now</dt>
                  <dd>{er.waitingCount}</dd>
                </div>
              </dl>
              <p className={styles.muted}>
                Updated {formatClock(new Date(er.updatedAt))}. The most serious cases are always seen first, so waits
                are estimates.
                {er.status === 'diverting' && ' Ambulances are being sent to other hospitals for now; you can still walk in.'}
              </p>
            </>
          ) : (
            <p className={styles.muted}>This hospital hasn’t reported its emergency status yet.</p>
          )}
          <p className={styles.urgent}>
            Life-threatening? Call <a href={`tel:${site.emergencyNumber}`}>{site.emergencyNumber}</a>.
          </p>
        </section>
      )}

      <section className={styles.card} aria-labelledby="duty-title">
        <h2 id="duty-title">On duty now</h2>
        {hospital.onDuty.length === 0 ? (
          <p className={styles.muted}>No specialists are on call at this moment.</p>
        ) : (
          <ul className={styles.duty}>
            {hospital.onDuty.map((d) => (
              <li key={d.specialty}>
                <span className={styles.specialty}>{d.specialty}</span>
                <span className={styles.count}>
                  {d.count} {d.count === 1 ? 'doctor' : 'doctors'}
                </span>
                {d.names && <span className={styles.names}>{d.names.join(', ')}</span>}
              </li>
            ))}
          </ul>
        )}
        {!hospital.namesShown && (
          <p className={styles.muted}>Doctors’ names are shown to signed-in hospital staff.</p>
        )}
      </section>

      {hospital.beds.length > 0 && (
        <section className={styles.card} aria-labelledby="beds-title">
          <h2 id="beds-title">Beds</h2>
          <ul className={styles.levels}>
            {hospital.beds.map((b) => (
              <li key={b.bedType}>
                <span>{TYPE_LABEL[b.bedType]}</span>
                <StatusBadge tone={BED_TONE[b.level]}>{BED_LEVEL_LABEL[b.level]}</StatusBadge>
              </li>
            ))}
          </ul>
          <p className={styles.muted}>Shown as levels: the hospital confirms a bed when you arrive.</p>
        </section>
      )}

      <section className={styles.card} aria-labelledby="services-title">
        <h2 id="services-title">Services and departments</h2>
        {hospital.services.length > 0 && (
          <ul className={styles.chips} aria-label="Services">
            {hospital.services.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        )}
        {hospital.departments.length > 0 ? (
          <ul className={styles.departments}>
            {hospital.departments.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        ) : (
          <p className={styles.muted}>No departments listed yet.</p>
        )}
      </section>
    </article>
  )
}
