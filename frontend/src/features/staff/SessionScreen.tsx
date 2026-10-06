import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { hospital } from '../../config/hospital'
import styles from './SessionScreen.module.css'

type SessionScreenProps = {
  title: string
  children?: ReactNode
  /** Show a link back to the public home page. */
  homeLink?: boolean
}

/** Full-page message shown before the staff workspace opens: checking sign-in, errors, wrong account type. */
export function SessionScreen({ title, children, homeLink = false }: SessionScreenProps) {
  return (
    <main id="main" className={styles.screen}>
      <p className={styles.brand}>{hospital.name}</p>
      <h1 className={styles.title}>{title}</h1>
      {children && <p>{children}</p>}
      {homeLink && (
        <Link to="/" className={styles.link}>
          Go to the home page
        </Link>
      )}
    </main>
  )
}
