import { Link } from 'react-router-dom'
import { hospital } from '../../config/hospital'
import styles from './Site.module.css'

function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path
        d="M6.6 3.5h3l1.5 4.2-2.1 1.5a12 12 0 0 0 5.8 5.8l1.5-2.1 4.2 1.5v3a2 2 0 0 1-2.2 2A17 17 0 0 1 4.6 5.7a2 2 0 0 1 2-2.2Z"
        fill="currentColor"
      />
    </svg>
  )
}

export function SiteHeader() {
  return (
    <header className={styles.header}>
      <div className={styles.headerInner}>
        <Link to="/" className={styles.brand}>
          <span className={styles.monogram} aria-hidden="true">
            {hospital.monogram}
          </span>
          <span className={styles.brandName}>{hospital.name}</span>
        </Link>
        <nav className={styles.headerNav} aria-label="Main">
          <a className={styles.emergency} href={`tel:${hospital.emergencyNumber}`}>
            <PhoneIcon />
            <span>
              Emergency: <span className={styles.number}>{hospital.emergencyNumber}</span>
            </span>
          </a>
          <Link className={styles.navLink} to="/login">
            Log in
          </Link>
          <Link className={`${styles.navLink} ${styles.navCta}`} to="/signup">
            Create account
          </Link>
        </nav>
      </div>
    </header>
  )
}
