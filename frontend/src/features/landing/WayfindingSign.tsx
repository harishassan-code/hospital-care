import { ER_STATUS_LABEL, type PublicStatus } from '../../api/publicStatus'
import { hospital } from '../../config/hospital'
import { FloorLines } from './FloorLines'
import { ALL_LINES, LINES } from './lines'
import { isInNow } from '../../lib/time'
import styles from './WayfindingSign.module.css'

type WayfindingSignProps = {
  status: PublicStatus | null
  failed: boolean
  now: Date
}

function details({ status, failed, now }: WayfindingSignProps): string[] {
  if (failed) return [`Call ${hospital.mainPhone} for current status`, 'Schedule unavailable', 'Patients and hospital staff']
  if (!status) return ['Checking…', 'Checking…', 'Patients and hospital staff']
  const { emergency, doctors } = status
  const inNow = doctors.filter((d) => isInNow(d, now)).length
  return [
    `${ER_STATUS_LABEL[emergency.status]} · about ${emergency.waitMinutes} min wait`,
    `${inNow} of ${doctors.length} doctors in now`,
    'Patients and hospital staff',
  ]
}

function DownArrow() {
  return (
    <svg className={styles.arrow} viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
      <path d="M12 3v16m0 0-6.5-6.5M12 19l6.5-6.5" fill="none" stroke="currentColor" strokeWidth="2.75" strokeLinecap="square" />
    </svg>
  )
}

/** The overhead direction sign: one row per destination on the page. */
export function WayfindingSign(props: WayfindingSignProps) {
  const text = details(props)

  return (
    <nav className={styles.sign} aria-label="On this page">
      {LINES.map((line, i) => (
        <a key={line.id} className={styles.row} href={`#${line.id}`} aria-busy={!props.status && !props.failed}>
          <FloorLines through={ALL_LINES.slice(0, i)} start={i} />
          <span className={styles.mobileChip} style={{ background: line.color }} aria-hidden="true" />
          <span className={styles.label}>{line.label}</span>
          <span className={styles.detail}>{text[i]}</span>
          <DownArrow />
        </a>
      ))}
    </nav>
  )
}
