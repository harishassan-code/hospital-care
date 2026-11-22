import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BLOOD_GROUPS, MINIMUM_STOCK } from '../../api/blood'
import { ER_STATUS_LABEL } from '../../api/publicStatus'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { summarize } from '../beds/beds'
import { availableCounts, stockLevel } from '../blood/blood'
import { EXPIRING_WITHIN_DAYS, expiresSoon, needsReorder } from '../pharmacy/pharmacy'
import { canSee } from '../staff/roles'
import { useStaff, type StaffData } from '../staff/staffContext'
import styles from './Overview.module.css'

type TileProps = { to: string; label: string; value: number; unit: string; detail?: string; note: ReactNode }

function Tile({ to, label, value, unit, detail, note }: TileProps) {
  return (
    <li>
      <Link to={to} className={styles.tile}>
        <span className={styles.tileLabel}>{label}</span>
        <span className={styles.tileValue}>
          {value} <span className={styles.tileUnit}>{unit}</span>
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

function EmergencyTile({ emergency }: { emergency: StaffData['emergency'] }) {
  if (!emergency) {
    return (
      <li>
        <Link to="/#emergency" className={styles.tile}>
          <span className={styles.tileLabel}>Emergency</span>
          <span className={styles.tileDetail}>Live status unavailable</span>
          <StatusBadge tone="neutral">Check with the ER desk</StatusBadge>
        </Link>
      </li>
    )
  }
  return (
    <Tile
      to="/#emergency"
      label="Emergency"
      value={emergency.waitingCount}
      unit="waiting"
      detail={`About ${emergency.waitMinutes} min wait`}
      note={
        <StatusBadge tone={emergency.status === 'accepting' ? 'ok' : 'warning'}>
          {ER_STATUS_LABEL[emergency.status]}
        </StatusBadge>
      }
    />
  )
}

export function StatusTiles({ data }: { data: StaffData }) {
  const { role, now } = useStaff()
  return (
    <ul className={styles.tiles} aria-label="Status summary">
      {canSee(role, 'beds') && <BedsTile data={data} />}
      <EmergencyTile emergency={data.emergency} />
      {canSee(role, 'blood') && <BloodTile data={data} />}
      {canSee(role, 'pharmacy') && <PharmacyTile data={data} now={now} />}
    </ul>
  )
}
