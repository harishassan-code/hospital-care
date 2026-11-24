import { useEffect, useState } from 'react'
import { getNetwork, listPublicHospitals, type NetworkSnapshot as Snapshot, type PublicHospital } from '../api/public'
import formStyles from '../components/form/Form.module.css'
import { SiteFooter } from '../components/layout/SiteFooter'
import { SiteHeader } from '../components/layout/SiteHeader'
import { hospital as site } from '../config/hospital'
import { CityNetwork } from '../features/landing/CityNetwork'
import { SignInOptions } from '../features/landing/SignInOptions'
import { HospitalDirectory } from '../features/network/HospitalDirectory'
import { HowItWorks } from '../features/network/HowItWorks'
import { PUBLIC_REFRESH_MS } from '../features/network/network'
import { NetworkSnapshot } from '../features/network/NetworkSnapshot'
import { useScrollToHash } from '../lib/useScrollToHash'
import styles from './LandingPage.module.css'

type Loaded<T> = { data: T | null; failed: boolean }

/**
 * The CityCare home page (B19): what the network is, the city right now, the member hospitals, and sign-in. Each
 * hospital's own details (its departments, who is on duty) are on its own page, not here.
 */
export default function LandingPage() {
  const [snapshot, setSnapshot] = useState<Loaded<Snapshot>>({ data: null, failed: false })
  const [hospitals, setHospitals] = useState<Loaded<PublicHospital[]>>({ data: null, failed: false })
  useScrollToHash(snapshot.data !== null || snapshot.failed)

  useEffect(() => {
    let active = true
    const load = () => {
      getNetwork()
        .then((data) => active && setSnapshot({ data, failed: false }))
        .catch(() => active && setSnapshot((s) => ({ data: s.data, failed: true })))
      listPublicHospitals()
        .then((data) => active && setHospitals({ data, failed: false }))
        .catch(() => active && setHospitals((h) => ({ data: h.data, failed: true })))
    }
    load()
    const timer = setInterval(() => {
      if (document.visibilityState !== 'hidden') load()
    }, PUBLIC_REFRESH_MS)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  return (
    <div className={styles.page}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <SiteHeader />

      <main id="main" className={styles.main}>
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.heroText}>
            <p className={styles.eyebrow}>The city’s hospital network</p>
            <h1 id="hero-title" className={styles.title}>
              Every hospital in the city, working as one.
            </h1>
            <p className={styles.lede}>
              {site.name} connects hospitals so an emergency gets the blood, beds, equipment, operating rooms and
              ambulances it needs, wherever in the city they are.
            </p>
            <div className={styles.heroActions}>
              <a href="#hospitals" className={formStyles.button}>
                Find a hospital
              </a>
              <a href="#sign-in" className={`${formStyles.button} ${formStyles.secondary}`}>
                Sign in
              </a>
            </div>
            <p className={styles.urgent}>
              Life-threatening? Call <a href={`tel:${site.emergencyNumber}`}>{site.emergencyNumber}</a> now.
            </p>
          </div>
          <CityNetwork className={styles.art} />
        </section>

        <section id="live" className={styles.section} aria-labelledby="live-title">
          <div className={styles.sectionHead}>
            <h2 id="live-title">The network right now</h2>
            <p className={styles.sectionLede}>Live from every member hospital.</p>
          </div>
          {snapshot.data ? (
            <NetworkSnapshot snapshot={snapshot.data} />
          ) : (
            <p className={styles.state}>
              {snapshot.failed ? 'Live status isn’t available right now. Try again in a minute.' : 'Loading the network…'}
            </p>
          )}
        </section>

        <section id="hospitals" className={styles.section} aria-labelledby="hospitals-title">
          <div className={styles.sectionHead}>
            <h2 id="hospitals-title">Hospitals in the network</h2>
            <p className={styles.sectionLede}>
              Choose a hospital to see its emergency department, services and who is on duty.
            </p>
          </div>
          {hospitals.data ? (
            <HospitalDirectory hospitals={hospitals.data} />
          ) : (
            <p className={styles.state}>
              {hospitals.failed ? 'The hospital list isn’t available right now.' : 'Loading hospitals…'}
            </p>
          )}
        </section>

        <section id="how" className={styles.section} aria-labelledby="how-title">
          <div className={styles.sectionHead}>
            <h2 id="how-title">How {site.name} works</h2>
            <p className={styles.sectionLede}>One network, shared by patients, hospitals and their staff.</p>
          </div>
          <HowItWorks />
        </section>

        <section id="sign-in" className={styles.section} aria-labelledby="sign-in-title">
          <div className={styles.sectionHead}>
            <h2 id="sign-in-title">Sign in</h2>
            <p className={styles.sectionLede}>One sign-in for patients and hospital staff.</p>
          </div>
          <SignInOptions />
        </section>
      </main>

      <SiteFooter />
    </div>
  )
}
