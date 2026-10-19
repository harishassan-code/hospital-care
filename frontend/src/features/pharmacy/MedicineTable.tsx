import { Fragment, useState } from 'react'
import type { Medicine } from '../../api/pharmacy'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatShortDate, fromDateKey } from '../../lib/time'
import {
  daysOfSupply,
  daysUntil,
  EXPIRING_WITHIN_DAYS,
  nearestExpiry,
  needsReorder,
  onHand,
  SUPPLY_CRITICAL_DAYS,
} from './pharmacy'
import styles from './Pharmacy.module.css'

function Supply({ medicine }: { medicine: Medicine }) {
  const days = daysOfSupply(medicine)
  if (!Number.isFinite(days)) return <>—</>
  const text = `${days} d`
  return days < SUPPLY_CRITICAL_DAYS ? <StatusBadge tone="critical">{text}</StatusBadge> : <>{text}</>
}

/** A batch expiry date, flagged when it falls inside the expiring-soon window. */
function ExpiryDate({ date, now }: { date: string; now: Date }) {
  const days = daysUntil(date, now)
  return (
    <span className={styles.inline}>
      {formatShortDate(fromDateKey(date), { year: true })}
      {days <= EXPIRING_WITHIN_DAYS && <StatusBadge tone="warning">{`in ${days} d`}</StatusBadge>}
    </span>
  )
}

export function MedicineTable({ medicines, now }: { medicines: Medicine[]; now: Date }) {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set())
  const toggle = (id: string) =>
    setOpen((current) => {
      const next = new Set(current)
      if (!next.delete(id)) next.add(id)
      return next
    })

  if (medicines.length === 0) return <p>No medicines match. Clear the search or choose another filter.</p>

  return (
    <div className="table-scroll">
      <table className={styles.table}>
        <caption className="visually-hidden">Medicine stock</caption>
        <thead>
          <tr>
            <th scope="col">Medicine</th>
            <th scope="col">Category</th>
            <th scope="col">On hand / reorder at</th>
            <th scope="col">Supply</th>
            <th scope="col">Nearest expiry</th>
            <th scope="col">Location</th>
            <th scope="col">
              <span className="visually-hidden">Batches</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {medicines.map((m) => {
            const expanded = open.has(m.id)
            const nearest = nearestExpiry(m)
            return (
              <Fragment key={m.id}>
                <tr data-medicine={m.id}>
                  <td>
                    <span className={styles.name}>{m.name}</span>
                    <span className={styles.form}>
                      {m.strength} · {m.form}
                    </span>
                    {(m.highAlert || m.controlled) && (
                      <span className={styles.flags}>
                        {m.highAlert && <span className={styles.flag}>High-alert</span>}
                        {m.controlled && (
                          <abbr className={styles.flag} title="Controlled drug: two-person check">
                            CD
                          </abbr>
                        )}
                      </span>
                    )}
                  </td>
                  <td>{m.category}</td>
                  <td className={styles.mono}>
                    <span className={styles.inline}>
                      <span>
                        {onHand(m)} / {m.reorderLevel} <span className={styles.unit}>{m.unit}</span>
                      </span>
                      {needsReorder(m) && <StatusBadge tone="warning">Reorder</StatusBadge>}
                    </span>
                  </td>
                  <td className={styles.mono}>
                    <Supply medicine={m} />
                  </td>
                  <td>{nearest ? <ExpiryDate date={nearest.expiresOn} now={now} /> : '—'}</td>
                  <td>{m.location}</td>
                  <td>
                    <button
                      type="button"
                      className={styles.toggle}
                      aria-expanded={expanded}
                      aria-controls={`batches-${m.id}`}
                      aria-label={`Batches for ${m.name}`}
                      onClick={() => toggle(m.id)}
                    >
                      Batches ({m.batches.length})
                    </button>
                  </td>
                </tr>
                {expanded && (
                  <tr id={`batches-${m.id}`} className={styles.batchRow}>
                    <td colSpan={7}>
                      <ul className={styles.batches} aria-label={`${m.name} batches`}>
                        {m.batches.map((b) => (
                          <li key={b.number}>
                            <span className={styles.mono}>{b.number}</span>
                            <ExpiryDate date={b.expiresOn} now={now} />
                            <span className={styles.mono}>
                              {b.quantity} {m.unit}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
