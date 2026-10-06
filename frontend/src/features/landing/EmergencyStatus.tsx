import { ER_STATUS_LABEL, type ErStatus, type PublicStatus } from '../../api/publicStatus'
import { hospital } from '../../config/hospital'
import styles from './EmergencyStatus.module.css'
import { formatClock } from './schedule'

const STATUS_ICON: Record<ErStatus, string> = {
  accepting: 'M5 12.5l4.5 4.5L19 7.5',
  busy: 'M12 6v8m0 3.5v.5',
  diverting: 'M6 12h12',
}

function StatusIcon({ status }: { status: ErStatus }) {
  return (
    <svg className={styles.icon} viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
      <path d={STATUS_ICON[status]} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="square" />
    </svg>
  )
}

const TRIAGE = [
  { level: 'Immediate', text: 'Life-threatening problems, such as a heart attack or heavy bleeding, are seen at once.' },
  { level: 'Urgent', text: 'Serious but stable problems, such as a broken bone or a high fever, are seen next.' },
  { level: 'Standard', text: 'Everything else is seen in the order people arrived.' },
]

type EmergencyStatusProps = {
  status: PublicStatus | null
  failed: boolean
}

export function EmergencyStatus({ status, failed }: EmergencyStatusProps) {
  return (
    <div className={styles.layout}>
      <div className={styles.now} aria-live="polite">
        {failed && (
          <p className={styles.message}>
            Live status isn’t available right now. Call {hospital.mainPhone} to ask about waiting times.
          </p>
        )}
        {!failed && !status && <p className={styles.message}>Checking the emergency department…</p>}
        {status && (
          <>
            <p className={styles.status}>
              <StatusIcon status={status.emergency.status} />
              {ER_STATUS_LABEL[status.emergency.status]}
            </p>
            <p className={styles.wait}>
              <span className={styles.waitLabel}>Estimated wait to be seen</span>
              <span className={styles.waitValue}>
                <span className={styles.approx}>about </span>
                {status.emergency.waitMinutes} min
              </span>
            </p>
            <p className={styles.meta}>
              {status.emergency.waitingCount} people waiting · updated {formatClock(new Date(status.updatedAt))}
            </p>
          </>
        )}
        <a className={styles.call} href={`tel:${hospital.emergencyNumber}`}>
          <span>Life-threatening? Don’t wait. Call</span>
          <span className={styles.callNumber}>{hospital.emergencyNumber}</span>
        </a>
      </div>

      <div className={styles.triage}>
        <h3 className={styles.triageTitle}>How we decide who’s seen first</h3>
        <ol className={styles.levels}>
          {TRIAGE.map((t) => (
            <li key={t.level}>
              <strong>{t.level}.</strong> {t.text}
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}
