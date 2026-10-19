import type { ReactNode } from 'react'
import styles from './Panel.module.css'

type PanelProps = {
  title: string
  id?: string
  /** Shown at the right of the title row, e.g. a link or a filter. */
  aside?: ReactNode
  children: ReactNode
}

/** A titled white card: the basic building block of staff pages. */
export function Panel({ title, id, aside, children }: PanelProps) {
  const headingId = `${id ?? title.toLowerCase().replace(/\W+/g, '-')}-title`
  return (
    <section id={id} className={styles.panel} aria-labelledby={headingId}>
      <header className={styles.head}>
        <h2 id={headingId} className={styles.title}>
          {title}
        </h2>
        {aside}
      </header>
      {children}
    </section>
  )
}
