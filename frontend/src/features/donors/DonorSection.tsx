import type { ReactNode } from 'react'
import styles from './Donors.module.css'

/** A titled part of the donor panel. The section is labelled by its heading. */
export function DonorSection({ title, children }: { title: string; children: ReactNode }) {
  const headingId = `donor-${title.toLowerCase().replace(/\W+/g, '-')}-heading`
  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h3 id={headingId}>{title}</h3>
      {children}
    </section>
  )
}
