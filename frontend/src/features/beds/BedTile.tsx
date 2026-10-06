import { useState, type CSSProperties } from 'react'
import type { Bed } from '../../api/beds'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { dateKey, formatDuration, formatShortDate, fromDateKey } from '../../lib/time'
import {
  actionsFor,
  CLEANING_TARGET_MINUTES,
  dayOfStay,
  isCleaningOverdue,
  ISOLATION_LABEL,
  minutesInStatus,
  STATUS_LABEL,
  type BedAction,
} from './beds'
import styles from './Beds.module.css'

const STATUS_COLOR: Record<Bed['status'], string> = {
  occupied: 'var(--bed-occupied)',
  reserved: 'var(--bed-reserved)',
  cleaning: 'var(--bed-cleaning)',
  free: 'var(--bed-free)',
  outOfService: 'var(--bed-out)',
}

function dischargeLabel(date: string, now: Date): string {
  const tomorrow = new Date(now)
  tomorrow.setDate(tomorrow.getDate() + 1)
  if (date === dateKey(now)) return 'Discharge today'
  if (date === dateKey(tomorrow)) return 'Discharge tomorrow'
  return `Discharge ${formatShortDate(fromDateKey(date))}`
}

type BedTileProps = {
  bed: Bed
  now: Date
  editable: boolean
  /** Resolves once the server has answered; the tile's buttons are disabled until then. */
  onAction: (action: BedAction) => Promise<void>
}

export function BedTile({ bed, now, editable, onAction }: BedTileProps) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const run = async (action: BedAction) => {
    setBusy(true)
    try {
      await onAction(action)
    } finally {
      setBusy(false)
    }
  }
  const status = STATUS_LABEL[bed.status]
  const overdue = isCleaningOverdue(bed, now)

  return (
    <li
      className={styles.tile}
      aria-labelledby={`${bed.id}-label ${bed.id}-status`}
      style={{ '--status': STATUS_COLOR[bed.status] } as CSSProperties}
    >
      <div className={styles.tileHead}>
        <span id={`${bed.id}-label`} className={styles.bedLabel}>
          {bed.label}
        </span>
        <span id={`${bed.id}-status`} className={styles.status}>
          <span className={styles.swatch} aria-hidden="true" />
          {status}
        </span>
      </div>

      {bed.status === 'occupied' && bed.patient ? (
        <div className={styles.details}>
          <p className={styles.patient}>
            {bed.patient.initials} · {bed.patient.age} {bed.patient.sex}
          </p>
          <p className={styles.meta}>
            Day {dayOfStay(bed, now)}
            {bed.expectedDischarge && (
              <>
                {' · '}
                <span className={bed.expectedDischarge === dateKey(now) ? styles.today : undefined}>
                  {dischargeLabel(bed.expectedDischarge, now)}
                </span>
              </>
            )}
          </p>
          {bed.isolation && <p className={styles.isolation}>{ISOLATION_LABEL[bed.isolation]}</p>}
        </div>
      ) : (
        <div className={styles.details}>
          <p className={styles.meta}>
            {status} for {formatDuration(minutesInStatus(bed, now))}
          </p>
          {overdue && <StatusBadge tone="warning">{`Over ${CLEANING_TARGET_MINUTES} min target`}</StatusBadge>}
        </div>
      )}

      {editable &&
        (confirming ? (
          <div className={styles.confirm}>
            <p>
              Discharge {bed.patient?.initials ?? 'patient'} from {bed.label}?
            </p>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.primaryAction}
                disabled={busy}
                onClick={() => {
                  setConfirming(false)
                  run('discharge')
                }}
              >
                Confirm discharge
              </button>
              <button type="button" className={styles.action} onClick={() => setConfirming(false)}>
                Keep patient
              </button>
            </div>
          </div>
        ) : (
          <div className={styles.actions}>
            {actionsFor(bed.status).map((t) => (
              <button
                key={t.action}
                type="button"
                className={styles.action}
                aria-label={`${t.label} ${bed.label}`}
                disabled={busy}
                onClick={() => (t.action === 'discharge' ? setConfirming(true) : run(t.action))}
              >
                {t.label}
              </button>
            ))}
          </div>
        ))}
    </li>
  )
}
