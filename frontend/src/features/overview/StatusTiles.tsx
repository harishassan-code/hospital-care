import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BLOOD_GROUPS, MINIMUM_STOCK } from '../../api/blood'
import { ER_STATUS_LABEL } from '../../api/public'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { useCountUp } from '../../lib/useCountUp'
import { summarize } from '../beds/beds'
import { availableCounts, stockLevel } from '../blood/blood'
import { EXPIRING_WITHIN_DAYS, expiresSoon, needsReorder } from '../pharmacy/pharmacy'
import { canSee } from '../staff/roles'
import { useStaff, type StaffData } from '../staff/staffContext'
import styles from './Overview.module.css'
import { summarizeRequests } from './requests'

type TileProps = { to: string; label: string; value: number; unit: string; detail?: string; note: ReactNode }

function Tile({ to, label, value, unit, detail, note }: TileProps) {
  const shown = useCountUp(value)
  return (
    <li>
      <Link to={to} className={styles.tile}>
        <span className={styles.tileLabel}>{label}</span>
        <span className={styles.tileValue}>
          {shown} <span className={styles.tileUnit}>{unit}</span>
        </span>
        {detail && <span className={styles.tileDetail}>{detail}</span>}
        {note}
      </Link>
    </li>
  )
}

function BedsTile({ data }: { data: StaffData }) {
  const all = summarize(data.beds)
  const icuFree = summarize(data.beds.filter((b) => b.ward === 'icu')).free
  return (
    <Tile
      to="/staff/beds"
      label="Beds free"
      value={all.free}
      unit={`of ${all.total} beds`}
      note={
        icuFree === 0 ? (
          <StatusBadge tone="critical">ICU full</StatusBadge>
        ) : (
          <StatusBadge tone="ok">{`${icuFree} ICU free`}</StatusBadge>
        )
      }
    />
  )
}

function BloodTile({ data }: { data: StaffData }) {
  const counts = availableCounts(data.units)
  const total = Object.values(counts).reduce((sum, byGroup) => sum + Object.values(byGroup).reduce((a, b) => a + b, 0), 0)
  const levels = BLOOD_GROUPS.map((g) => stockLevel(counts.redCells[g], MINIMUM_STOCK.redCells[g]))
  const low = levels.filter((l) => l !== 'ok').length
  const tone = levels.includes('critical') ? 'critical' : low ? 'warning' : 'ok'
  return (
    <Tile
      to="/staff/blood"
      label="Blood bank"
      value={total}
      unit="units available"
      note={<StatusBadge tone={tone}>{low ? `${low} red-cell groups low` : 'All groups above minimum'}</StatusBadge>}
    />
  )
}

function PharmacyTile({ data, now }: { data: StaffData; now: Date }) {
  const reorder = data.medicines.filter(needsReorder).length
  const expiring = data.medicines.filter((m) => expiresSoon(m, now)).length
  return (
    <Tile
      to="/staff/pharmacy"
      label="Pharmacy"
      value={reorder}
      unit={reorder === 1 ? 'item to reorder' : 'items to reorder'}
      note={
        <StatusBadge tone={expiring ? 'warning' : 'ok'}>
          {expiring ? `${expiring} expiring within ${EXPIRING_WITHIN_DAYS} days` : 'No stock expiring soon'}
        </StatusBadge>
      }
    />
  )
}

/** Where staff update our emergency department's status (B19). */
export const DEPARTMENT_LINK = '/staff/emergencies#department'

function EmergencyTile({ emergency }: { emergency: StaffData['emergency'] }) {
  if (!emergency || emergency.status === null) {
    return (
      <li>
        <Link to={DEPARTMENT_LINK} className={styles.tile}>
          <span className={styles.tileLabel}>Emergency</span>
          <span className={styles.tileDetail}>{emergency ? 'Status not reported yet' : 'Live status unavailable'}</span>
          <StatusBadge tone="neutral">{emergency ? 'Report it' : 'Check with the ER desk'}</StatusBadge>
        </Link>
      </li>
    )
  }
  return (
    <Tile
      to={DEPARTMENT_LINK}
      label="Emergency"
      value={emergency.waitingCount ?? 0}
      unit="waiting"
      detail={`About ${emergency.waitMinutes ?? 0} min wait`}
      note={
        <StatusBadge tone={emergency.status === 'accepting' ? 'ok' : 'warning'}>
          {ER_STATUS_LABEL[emergency.status]}
        </StatusBadge>
      }
    />
  )
}

/** A tile whose figures couldn't be loaded: it says so, and points to the page that has the detail. */
function UnavailableTile({ to, label, check }: { to: string; label: string; check: string }) {
  return (
    <li>
      <Link to={to} className={styles.tile}>
        <span className={styles.tileLabel}>{label}</span>
        <span className={styles.tileDetail}>Unavailable</span>
        <StatusBadge tone="neutral">{check}</StatusBadge>
      </Link>
    </li>
  )
}

function OpenRequestsTile({ cases }: { cases: { open: number; critical: number } | null }) {
  if (!cases) return <UnavailableTile to="/staff/emergencies" label="Open requests" check="Check the Emergencies page" />
  return (
    <Tile
      to="/staff/emergencies"
      label="Open requests"
      value={cases.open}
      unit={cases.open === 1 ? 'open case' : 'open cases'}
      note={
        cases.critical ? (
          <StatusBadge tone="critical">{`${cases.critical} critical`}</StatusBadge>
        ) : (
          <StatusBadge tone="ok">None critical</StatusBadge>
        )
      }
    />
  )
}

function TransfersTile({ transfers }: { transfers: { pending: number; toAnswer: number; outgoing: number } | null }) {
  if (!transfers) return <UnavailableTile to="/staff/transfers" label="Transfers" check="Check the Transfers page" />
  return (
    <Tile
      to="/staff/transfers"
      label="Transfers"
      value={transfers.pending}
      unit={transfers.pending === 1 ? 'pending transfer' : 'pending transfers'}
      detail={`${transfers.toAnswer} to answer · ${transfers.outgoing} outgoing`}
      note={
        transfers.toAnswer ? (
          <StatusBadge tone="warning">{`${transfers.toAnswer} waiting for an answer`}</StatusBadge>
        ) : (
          <StatusBadge tone="ok">Nothing to answer</StatusBadge>
        )
      }
    />
  )
}

export function StatusTiles({ data }: { data: StaffData }) {
  const { role, now } = useStaff()
  const requests = summarizeRequests(data.cases, data.transfers)
  return (
    <ul className={styles.tiles} aria-label="Status summary">
      {canSee(role, 'beds') && <BedsTile data={data} />}
      <EmergencyTile emergency={data.emergency} />
      {canSee(role, 'emergencies') && <OpenRequestsTile cases={requests.cases} />}
      {canSee(role, 'transfers') && <TransfersTile transfers={requests.transfers} />}
      {canSee(role, 'blood') && <BloodTile data={data} />}
      {canSee(role, 'pharmacy') && <PharmacyTile data={data} now={now} />}
    </ul>
  )
}
