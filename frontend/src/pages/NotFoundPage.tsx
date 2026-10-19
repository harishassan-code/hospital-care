import { Link } from 'react-router-dom'
import { hospital } from '../config/hospital'
import styles from './NotFoundPage.module.css'

export default function NotFoundPage() {
  return (
    <main id="main" className={styles.page}>
      <p className={styles.code}>404</p>
      <h1 className={styles.title}>This page doesn’t exist</h1>
      <p>The link may be old, or the address may have a typo.</p>
      <Link className={styles.home} to="/">
        ← Back to {hospital.name}
      </Link>
    </main>
  )
}
