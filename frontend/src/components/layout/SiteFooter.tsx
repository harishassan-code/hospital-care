import { Link } from 'react-router-dom'
import { hospital as site } from '../../config/hospital'
import styles from './Site.module.css'

/** The public footer: the network's own contact details (each hospital's are on its page) and the main sections. */
export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerInner}>
        <p className={styles.footerName}>{site.name}</p>
        <dl className={styles.facts}>
          <div>
            <dt>Emergency</dt>
            <dd>
              <a href={`tel:${site.emergencyNumber}`}>{site.emergencyNumber}</a>
            </dd>
          </div>
          <div>
            <dt>Network help desk</dt>
            <dd>
              <a href={`tel:${site.mainPhone.replace(/[^\d+]/g, '')}`}>{site.mainPhone}</a>
            </dd>
          </div>
          <div>
            <dt>Network office</dt>
            <dd>{site.address}</dd>
          </div>
          <div>
            <dt>On this site</dt>
            <dd>
              <ul className={styles.footerLinks}>
                <li>
                  <Link to="/#hospitals">Hospitals</Link>
                </li>
                <li>
                  <Link to="/#how">How it works</Link>
                </li>
                <li>
                  <Link to="/privacy">Patient privacy</Link>
                </li>
                <li>
                  <Link to="/login">Sign in</Link>
                </li>
              </ul>
            </dd>
          </div>
        </dl>
        <p className={styles.poweredBy}>
          {site.name} connects the city’s hospitals to share blood, beds, equipment, operating rooms and ambulances in an
          emergency. Each hospital’s visiting hours and contacts are on its own page.
        </p>
      </div>
    </footer>
  )
}
