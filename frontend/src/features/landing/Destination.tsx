import type { CSSProperties, ReactNode } from 'react'
import styles from './Destination.module.css'
import { RailRow } from './FloorLines'
import { ALL_LINES, LINES } from './lines'

type DestinationProps = {
  /** Position in LINES; decides the colour and which floor line turns in here. */
  index: number
  lede: string
  children: ReactNode
}

/** A page section that a floor line leads to. Lines for later destinations keep running past it. */
export function Destination({ index, lede, children }: DestinationProps) {
  const line = LINES[index]
  const later = ALL_LINES.slice(index + 1)
  const headingId = `${line.id}-title`

  return (
    <section
      id={line.id}
      className={styles.destination}
      aria-labelledby={headingId}
      style={{ '--c': line.color } as CSSProperties}
    >
      <RailRow lines={{ through: [index, ...later] }} className={styles.approach} />
      <RailRow lines={{ through: later, turn: index }}>
        <h2 id={headingId} className={styles.title}>
          <span className={styles.plate} aria-hidden="true" />
          {line.label}
        </h2>
      </RailRow>
      <RailRow lines={{ through: later }} className={styles.body}>
        <p className={styles.lede}>{lede}</p>
        {children}
      </RailRow>
    </section>
  )
}
