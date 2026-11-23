import { useId, useState, type ReactNode } from 'react'
import styles from './Charts.module.css'

export interface LegendItem {
  label: string
  color: string
  /** How the series is drawn, so the legend matches it: a line, a band, a dashed line or a bar. */
  mark?: 'line' | 'band' | 'dashed' | 'bar'
}

export interface ChartTable {
  columns: string[]
  rows: (string | number)[][]
}

type ChartFrameProps = {
  title: string
  /** One sentence on what the chart shows, read by screen readers as the chart's name too. */
  summary: string
  legend?: LegendItem[]
  table: ChartTable
  /** When the figures were read. */
  updatedAt?: Date | null
  state?: 'loading' | 'failed' | 'empty' | 'ready'
  empty?: string
  children: ReactNode
}

const time = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' })

/**
 * A chart with its title, what it shows, a legend, when it was updated, and a "Show as table" switch: the same
 * figures as a table, for screen readers and anyone who prefers numbers (B22).
 */
export function ChartFrame({ title, summary, legend, table, updatedAt, state = 'ready', empty, children }: ChartFrameProps) {
  const [asTable, setAsTable] = useState(false)
  const id = useId()
  return (
    <figure className={styles.frame} aria-labelledby={`${id}-title`}>
      <figcaption className={styles.head}>
        <span>
          <span id={`${id}-title`} className={styles.title}>
            {title}
          </span>
          <span className={styles.summary}>{summary}</span>
        </span>
        {state === 'ready' && (
          <button type="button" className={styles.toggle} aria-pressed={asTable} onClick={() => setAsTable((v) => !v)}>
            {asTable ? 'Show as chart' : 'Show as table'}
          </button>
        )}
      </figcaption>
      {state === 'loading' && <p className={styles.note}>Loading the figures…</p>}
      {state === 'failed' && <p className={styles.note}>The figures couldn’t be loaded. They’ll try again shortly.</p>}
      {state === 'empty' && <p className={styles.note}>{empty ?? 'No figures for this period yet.'}</p>}
      {state === 'ready' &&
        (asTable ? (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <caption className="visually-hidden">{title}</caption>
              <thead>
                <tr>
                  {table.columns.map((c) => (
                    <th key={c} scope="col">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) =>
                      j === 0 ? (
                        <th key={j} scope="row">
                          {cell}
                        </th>
                      ) : (
                        <td key={j}>{cell}</td>
                      ),
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <>
            {legend && legend.length > 0 && (
              <ul className={styles.legend} aria-label="Legend">
                {legend.map((item) => (
                  <li key={item.label}>
                    <span className={`${styles.key} ${styles[item.mark ?? 'line']}`} style={{ color: item.color }} aria-hidden="true" />
                    {item.label}
                  </li>
                ))}
              </ul>
            )}
            {children}
          </>
        ))}
      {updatedAt && state === 'ready' && <p className={styles.updated}>Updated {time.format(updatedAt)}</p>}
    </figure>
  )
}

/** A grid of charts: two columns where there is room. */
export function ChartGrid({ children }: { children: ReactNode }) {
  return <div className={styles.chartGrid}>{children}</div>
}
