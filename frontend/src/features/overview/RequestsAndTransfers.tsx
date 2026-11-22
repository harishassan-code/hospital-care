import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCases, type EmergencyCase } from '../../api/emergencies'
import { listTransfers, TRANSFER_STATUS_LABEL, type Transfer } from '../../api/transfers'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { SEVERITY_TONE, STATUS_LABEL } from '../emergencies/emergencies'
import { canSee } from '../staff/roles'
import { useStaff } from '../staff/staffContext'

export const REFRESH_MS = 60_000
const FINISHED = ['fulfilled', 'closed', 'cancelled']
const MOVING = ['approved', 'dispatched', 'inTransit']

/** Reload `load` every minute while the tab is visible (story #54: refreshes without a page reload). */
function usePolled<T>(load: () => Promise<T>, enabled: boolean): T | null {
  const [data, setData] = useState<T | null>(null)
  useEffect(() => {
    if (!enabled) return
    let active = true
    const run = () => load().then((d) => active && setData(d)).catch(() => undefined)
    void run()
    const timer = setInterval(() => document.visibilityState !== 'hidden' && void run(), REFRESH_MS)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [load, enabled])
  return data
}

/** Open emergencies and pending transfers on the hospital dashboard (story #54). */
export function RequestsAndTransfers() {
  const { role, user } = useStaff()
  const seesCases = canSee(role, 'emergencies')
  const seesTransfers = canSee(role, 'transfers')
  const cases = usePolled(getCases, seesCases)
  const loadTransfers = useCallback(() => listTransfers(), [])
  const transfers = usePolled(loadTransfers, seesTransfers)

  const open = (cases ?? []).filter((c: EmergencyCase) => !FINISHED.includes(c.status))
  const mine = user.hospital?.id
  const incoming = (transfers ?? []).filter((t: Transfer) => t.status === 'requested' && (mine === undefined || t.supplier.id === mine))
  const onTheWay = (transfers ?? []).filter((t: Transfer) => MOVING.includes(t.status))

  return (
    <>
      {seesCases && (
        <Panel title="Open emergencies" aside={<Link to="/staff/emergencies">All cases</Link>}>
          {cases === null ? (
            <p>Loading…</p>
          ) : open.length === 0 ? (
            <p>No open emergencies.</p>
          ) : (
            <ul aria-label="Open emergencies">
              {open.slice(0, 8).map((c) => (
                <li key={c.id}>
                  <StatusBadge tone={SEVERITY_TONE[c.severity]}>{c.severity}</StatusBadge>{' '}
                  <Link to={`/staff/emergencies/${c.id}`}>{c.id}</Link> · {STATUS_LABEL[c.status]}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}
      {seesTransfers && (
        <Panel title="Pending transfers" aside={<Link to="/staff/transfers">All transfers</Link>}>
          {transfers === null ? (
            <p>Loading…</p>
          ) : incoming.length + onTheWay.length === 0 ? (
            <p>No transfers waiting.</p>
          ) : (
            <ul aria-label="Pending transfers">
              {incoming.map((t) => (
                <li key={t.id}>
                  <strong>Waiting for your answer:</strong> {t.quantity} × {t.need} for {t.receiver.name}
                </li>
              ))}
              {onTheWay.map((t) => (
                <li key={t.id}>
                  {TRANSFER_STATUS_LABEL[t.status]}: {t.quantity} × {t.need}, {t.supplier.name} → {t.receiver.name}
                  {t.trip ? ` (${t.trip.ambulance.identifier})` : ''}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}
    </>
  )
}
