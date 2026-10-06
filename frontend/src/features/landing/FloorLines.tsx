import type { CSSProperties, ReactNode } from 'react'
import styles from './FloorLines.module.css'
import { LINES } from './lines'

type FloorLinesProps = {
  /** Lines that pass straight through this row. */
  through?: number[]
  /** Line that starts in this row (at its vertical middle) and runs down. Drawn with a station marker. */
  start?: number
  /** Line that arrives from above and turns right into the content at the row's vertical middle. */
  turn?: number
}

function lineStyle(index: number): CSSProperties {
  return { '--x': `${72 - index * 24}px`, '--c': LINES[index].color } as CSSProperties
}

export function FloorLines({ through = [], start, turn }: FloorLinesProps) {
  return (
    <div className={styles.gutter} aria-hidden="true">
      {through.map((i) => (
        <span key={i} className={`${styles.line} ${styles.through}`} style={lineStyle(i)} />
      ))}
      {start !== undefined && (
        <>
          <span className={`${styles.line} ${styles.start}`} style={lineStyle(start)} />
          <span className={styles.station} style={lineStyle(start)} />
        </>
      )}
      {turn !== undefined && (
        <>
          <span className={`${styles.line} ${styles.arrive}`} style={lineStyle(turn)} />
          <span className={`${styles.line} ${styles.across}`} style={lineStyle(turn)} />
        </>
      )}
    </div>
  )
}

/**
 * A two-column row: floor-line gutter on the left, content on the right.
 * `className` styles the content cell, so padding there never leaves gaps in the lines.
 */
export function RailRow({
  lines,
  className,
  children,
}: {
  lines: FloorLinesProps
  className?: string
  children?: ReactNode
}) {
  return (
    <div className={styles.row}>
      <FloorLines {...lines} />
      <div className={`${styles.content} ${className ?? ''}`}>{children}</div>
    </div>
  )
}
