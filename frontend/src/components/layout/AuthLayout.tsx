import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { hospital } from '../../config/hospital'
import styles from './AuthLayout.module.css'

type AuthLayoutProps = {
  /** Sign-row text, also the page's h1 (e.g. "Sign in"). */
  title: string
  children: ReactNode
  /** Links under the card, e.g. "New patient? Create an account". */
  footer?: ReactNode
}

/**
 * Dark sign band with a teal sign row; the teal floor line runs from the sign down the
 * left edge of the form card, so the eye "follows the line" into the form.
 */
export function AuthLayout({ title, children, footer }: AuthLayoutProps) {
  return (
    <div className={styles.page}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className={styles.band}>
        <div className={styles.column}>
          <Link className={styles.back} to="/">
            <span aria-hidden="true">←</span> {hospital.name}
          </Link>
          <div className={styles.signRow}>
            <h1 className={styles.title}>{title}</h1>
          </div>
        </div>
      </header>
      <main id="main" className={styles.main}>
        <div className={`${styles.column} ${styles.track}`}>
          <div className={styles.card}>{children}</div>
          {footer && <div className={styles.footer}>{footer}</div>}
        </div>
      </main>
    </div>
  )
}
