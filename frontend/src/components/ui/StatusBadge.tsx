import type { ReactNode } from 'react'
import styles from './StatusBadge.module.css'

export type Tone = 'ok' | 'warning' | 'critical' | 'neutral'

/** Each tone has its own shape, so status never depends on colour alone. */
const ICON: Record<Tone, ReactNode> = {
  ok: <path d="M4 8.5l2.6 2.6L12 5.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square" />,
  warning: (
    <>
      <path d="M8 1.8 15 14.2H1Z" fill="currentColor" />
      <path d="M8 6v4m0 1.6v.6" stroke="#fff" strokeWidth="1.8" />
    </>
  ),
  critical: (
    <>
      <path d="M5 1h6l4 4v6l-4 4H5l-4-4V5Z" fill="currentColor" />
      <path d="M8 4.2v4.6m0 1.8v.8" stroke="#fff" strokeWidth="1.9" />
    </>
  ),
  neutral: <circle cx="8" cy="8" r="3.5" fill="currentColor" />,
}

export function StatusBadge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`}>
      <svg className={styles.icon} viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
        {ICON[tone]}
      </svg>
      {children}
    </span>
  )
}
