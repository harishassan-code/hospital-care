import { ArrowRight, Droplet, LocateFixed, MapPin } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { PublicHospital } from '../../api/public'
import { ErStatusLine } from './ErStatusLine'
import { areaOf, distanceKm, formatDistance, sortHospitals, type Place } from './network'
import styles from './Network.module.css'

const SHOWN_SERVICES = 4

type Locating = 'idle' | 'asking' | 'denied' | 'unsupported'

/**
 * The member hospitals (B19), shortest emergency wait first, or nearest first once the visitor shares their
 * location. The location stays in the browser: distances are worked out here and never sent anywhere.
 */
export function HospitalDirectory({ hospitals }: { hospitals: PublicHospital[] }) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [locating, setLocating] = useState<Locating>('idle')

  function locate() {
    if (!('geolocation' in navigator)) {
      setLocating('unsupported')
      return
    }
    setLocating('asking')
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setOrigin({ latitude: position.coords.latitude, longitude: position.coords.longitude })
        setLocating('idle')
      },
      () => setLocating('denied'),
      { maximumAge: 300_000, timeout: 15_000 },
    )
  }

  const ordered = sortHospitals(hospitals, origin)

  return (
    <div className={styles.directory}>
      <div className={styles.directoryBar}>
        <p className={styles.muted} aria-live="polite">
          {origin
            ? 'Nearest first. Your location stays on this device.'
            : 'Shortest emergency wait first.'}
          {locating === 'denied' && ' Location wasn’t shared, so they stay in order of waiting time.'}
          {locating === 'unsupported' && ' This browser can’t share a location.'}
        </p>
        {origin ? (
          <button type="button" className={styles.locate} onClick={() => setOrigin(null)}>
            Sort by waiting time
          </button>
        ) : (
          <button type="button" className={styles.locate} onClick={locate} disabled={locating === 'asking'}>
            <LocateFixed aria-hidden="true" size={18} />
            {locating === 'asking' ? 'Finding you…' : 'Use my location'}
          </button>
        )}
      </div>
      {ordered.length === 0 ? (
        <p>No hospitals have joined the network yet.</p>
      ) : (
        <ul className={styles.cards}>
          {ordered.map((h) => (
            <li key={h.id} className={styles.card}>
              <div className={styles.cardHead}>
                <h3 className={styles.cardTitle}>
                  <Link to={`/hospitals/${h.id}`} className={styles.cardLink}>
                    {h.name}
                  </Link>
                </h3>
                {h.type === 'bloodBank' && (
                  <span className={styles.kind}>
                    <Droplet aria-hidden="true" size={14} /> Blood bank
                  </span>
                )}
              </div>
              <p className={styles.area}>
                <MapPin aria-hidden="true" size={15} />
                {areaOf(h.address)}
                {origin && <span className={styles.distance}> · {formatDistance(distanceKm(origin, h))}</span>}
              </p>
              {h.type !== 'bloodBank' && <ErStatusLine emergency={h.emergency} />}
              {h.services.length > 0 && (
                <ul className={styles.chips} aria-label="Services">
                  {h.services.slice(0, SHOWN_SERVICES).map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                  {h.services.length > SHOWN_SERVICES && <li>+{h.services.length - SHOWN_SERVICES} more</li>}
                </ul>
              )}
              <span className={styles.cardMore} aria-hidden="true">
                View hospital <ArrowRight size={16} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
