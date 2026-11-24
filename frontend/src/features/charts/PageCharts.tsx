import { useEffect, useState } from 'react'
import { BLOOD_GROUPS, MINIMUM_STOCK, type BloodUnit } from '../../api/blood'
import type { Bed, Ward } from '../../api/beds'
import type { CommandCentre } from '../../api/commandCentre'
import type { EmergencyCase } from '../../api/emergencies'
import { getOperatingRoomSchedule, type OperatingRoomSchedule } from '../../api/operatingRooms'
import type { Medicine } from '../../api/pharmacy'
import type { Report } from '../../api/reports'
import type { Transfer } from '../../api/transfers'
import { BarChart, ChartFrame, ChartGrid, SERIES, Sparkline, Timeline } from '../../components/charts'
import { cityNow } from '../../lib/cityClock'
import { availableCounts, formatGroup, stockLevel } from '../blood/blood'
import { MetricChart } from './MetricChart'
import { points, useMetrics } from './useMetrics'
import styles from './PageCharts.module.css'

const DAY = 86_400_000
const karachiDay = (t: number | string | Date) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Karachi' }).format(new Date(t))
const dayLabel = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', weekday: 'short', day: 'numeric' })

/** The last `n` Karachi days, oldest first, as "YYYY-MM-DD". */
function lastDays(n: number): string[] {
  const today = cityNow().getTime()
  return Array.from({ length: n }, (_, i) => karachiDay(today - (n - 1 - i) * DAY))
}

const label = (day: string) => dayLabel.format(Date.parse(`${day}T07:00:00Z`))

// ── Overview ────────────────────────────────────────────────────────────────────────────────────────

export function OverviewCharts({ beds }: { beds: boolean }) {
  return (
    <ChartGrid>
      <MetricChart
        title="Emergency arrivals and departures"
        summary="Patients arriving and leaving the emergency department each hour today, against a typical day."
        typical
        valueSuffix="patients"
        lines={[
          { label: 'Arrivals', metric: 'er.arrivals', color: SERIES[0] },
          { label: 'Departures', metric: 'er.departures', color: SERIES[1] },
        ]}
      />
      {beds && (
        <MetricChart
          title="Bed occupancy, last 7 days"
          summary="Share of beds in service with a patient in them, hour by hour."
          days={7}
          lines={[{ label: 'Occupied', metric: 'beds.occupied', per: 'beds.in_service', color: SERIES[0] }]}
          threshold={{ value: 90, label: 'Nearly full' }}
        />
      )}
    </ChartGrid>
  )
}

// ── Beds ────────────────────────────────────────────────────────────────────────────────────────────

export function BedsCharts({ beds, wards }: { beds: Bed[]; wards: Ward[] }) {
  const today = karachiDay(cityNow())
  const rows = wards
    .map((w) => {
      const mine = beds.filter((b) => b.ward === w.id)
      return {
        ward: w.name,
        cleaning: mine.filter((b) => b.status === 'cleaning').length,
        dueHome: mine.filter((b) => b.status === 'occupied' && b.expectedDischarge && b.expectedDischarge <= today).length,
      }
    })
    .filter((r) => r.cleaning + r.dueHome > 0)
  return (
    <ChartGrid>
      <MetricChart
        title="Occupancy by bed type, last 7 days"
        summary="Share of each kind of bed with a patient in it."
        days={7}
        lines={[
          { label: 'Intensive care', metric: 'beds.occupied.icu', per: 'beds.in_service.icu', color: SERIES[0] },
          { label: 'General', metric: 'beds.occupied.general', per: 'beds.in_service.general', color: SERIES[1] },
          { label: 'Emergency', metric: 'beds.occupied.emergency', per: 'beds.in_service.emergency', color: SERIES[2] },
        ]}
      />
      <ChartFrame
        title="Beds freeing up in the next 12 hours"
        summary="By ward: beds being cleaned now, and patients due home today."
        legend={[
          { label: 'Being cleaned', color: SERIES[1], mark: 'bar' },
          { label: 'Due home today', color: SERIES[0], mark: 'bar' },
        ]}
        table={{ columns: ['Ward', 'Being cleaned', 'Due home today'], rows: rows.map((r) => [r.ward, r.cleaning, r.dueHome]) }}
        state={rows.length ? 'ready' : 'empty'}
        empty="No beds are being cleaned and nobody is due home today."
      >
        <BarChart
          label="Beds freeing up by ward"
          bars={rows.map((r) => ({
            label: r.ward,
            segments: [
              { key: 'cleaning', label: 'Being cleaned', value: r.cleaning, color: SERIES[1] },
              { key: 'due', label: 'Due home today', value: r.dueHome, color: SERIES[0] },
            ],
          }))}
        />
      </ChartFrame>
    </ChartGrid>
  )
}

// ── Blood ───────────────────────────────────────────────────────────────────────────────────────────

export function BloodCharts({ units }: { units: BloodUnit[] }) {
  const counts = availableCounts(units).redCells
  const flag = { low: 'Low', critical: 'Critical' } as const
  return (
    <ChartGrid>
      <ChartFrame
        title="Red cells by group"
        summary="Usable red-cell units in each group, against the group's minimum (dashed)."
        table={{
          columns: ['Group', 'Usable', 'Minimum'],
          rows: BLOOD_GROUPS.map((g) => [formatGroup(g), counts[g], MINIMUM_STOCK.redCells[g]]),
        }}
      >
        <BarChart
          label="Red cells by group against the minimum"
          thresholds={BLOOD_GROUPS.map((g) => MINIMUM_STOCK.redCells[g])}
          bars={BLOOD_GROUPS.map((g) => {
            const level = stockLevel(counts[g], MINIMUM_STOCK.redCells[g])
            return {
              label: formatGroup(g),
              segments: [{ key: 'n', label: 'Usable', value: counts[g], color: SERIES[0] }],
              note: `${counts[g]} / min ${MINIMUM_STOCK.redCells[g]}`,
              flag: level === 'ok' ? undefined : flag[level],
            }
          })}
        />
      </ChartFrame>
      <MetricChart
        title="Issued and donated, last 14 days"
        summary="Units given out and units donated each day."
        days={14}
        bucket="day"
        valueSuffix="units"
        lines={[
          { label: 'Issued', metric: 'blood.issued', color: SERIES[0] },
          { label: 'Donated', metric: 'blood.donated', color: SERIES[1] },
        ]}
      />
    </ChartGrid>
  )
}

export function DonorsCharts() {
  return (
    <MetricChart
      title="Donations, last 14 days"
      summary="Donations taken each day."
      days={14}
      bucket="day"
      valueSuffix="donations"
      lines={[{ label: 'Donations', metric: 'blood.donated', color: SERIES[1] }]}
    />
  )
}

// ── Equipment, ambulances ──────────────────────────────────────────────────────────────────────────

export function EquipmentCharts() {
  return (
    <MetricChart
      title="Ventilators in use, last 24 hours"
      summary="Ventilators on a patient each hour."
      valueSuffix="in use"
      lines={[{ label: 'Ventilators in use', metric: 'equipment.ventilators_in_use', color: SERIES[0] }]}
    />
  )
}

export function AmbulancesCharts() {
  return (
    <ChartGrid>
      <MetricChart
        title="Ambulance trips per hour"
        summary="Trips each hour today, against a typical day."
        typical
        valueSuffix="trips"
        lines={[{ label: 'Trips', metric: 'ambulances.trips', color: SERIES[0] }]}
      />
      <MetricChart
        title="Trips per day, last 7 days"
        summary="Ambulance trips each day."
        days={7}
        bucket="day"
        valueSuffix="trips"
        lines={[{ label: 'Trips', metric: 'ambulances.trips', color: SERIES[0] }]}
      />
    </ChartGrid>
  )
}

// ── Pharmacy ────────────────────────────────────────────────────────────────────────────────────────

export function PharmacyCharts({ medicines }: { medicines: Medicine[] }) {
  const rows = medicines
    .filter((m) => m.dailyUse > 0)
    .map((m) => {
      const stock = m.batches.reduce((sum, b) => sum + b.quantity, 0)
      return { name: m.name, days: Math.round((stock / m.dailyUse) * 10) / 10, reorderDays: Math.round((m.reorderLevel / m.dailyUse) * 10) / 10 }
    })
    .sort((a, b) => a.days - a.reorderDays - (b.days - b.reorderDays))
    .slice(0, 8)
  return (
    <ChartFrame
      title="Days of stock left"
      summary="The medicines nearest their reorder level: days their stock lasts at the usual daily use, against the reorder point (dashed)."
      table={{ columns: ['Medicine', 'Days of stock', 'Reorder at (days)'], rows: rows.map((r) => [r.name, r.days, r.reorderDays]) }}
      state={rows.length ? 'ready' : 'empty'}
      empty="No medicine has a daily use recorded."
    >
      <BarChart
        label="Days of stock left by medicine"
        thresholds={rows.map((r) => r.reorderDays)}
        bars={rows.map((r) => ({
          label: r.name,
          segments: [{ key: 'days', label: 'Days of stock', value: r.days, color: SERIES[0] }],
          note: `${r.days} days`,
          flag: r.days <= r.reorderDays ? 'Reorder' : undefined,
        }))}
      />
    </ChartFrame>
  )
}

// ── Transfers, cases ────────────────────────────────────────────────────────────────────────────────

export function TransfersCharts({ incoming, outgoing }: { incoming: Transfer[]; outgoing: Transfer[] }) {
  const days = lastDays(14)
  const count = (list: Transfer[], day: string) => list.filter((t) => karachiDay(t.createdAt) === day).length
  const rows = days.map((d) => ({ day: d, in: count(incoming, d), out: count(outgoing, d) }))
  return (
    <ChartFrame
      title="Transfers per day, last 14 days"
      summary="Transfers asked of other hospitals (to us) and of us (from us), by the day they were asked."
      legend={[
        { label: 'To us', color: SERIES[0], mark: 'bar' },
        { label: 'From us', color: SERIES[1], mark: 'bar' },
      ]}
      table={{ columns: ['Day', 'To us', 'From us'], rows: rows.map((r) => [label(r.day), r.in, r.out]) }}
      state={rows.some((r) => r.in + r.out) ? 'ready' : 'empty'}
      empty="No transfers in the last 14 days."
    >
      <BarChart
        label="Transfers per day"
        bars={rows.map((r) => ({
          label: label(r.day),
          segments: [
            { key: 'in', label: 'To us', value: r.in, color: SERIES[0] },
            { key: 'out', label: 'From us', value: r.out, color: SERIES[1] },
          ],
        }))}
      />
    </ChartFrame>
  )
}

const SEVERITIES = [
  { id: 'critical', label: 'Critical', color: SERIES[2] },
  { id: 'high', label: 'High', color: SERIES[1] },
  { id: 'moderate', label: 'Moderate', color: SERIES[0] },
  { id: 'low', label: 'Low', color: 'var(--bed-out)' },
] as const

export function CasesCharts({ cases }: { cases: EmergencyCase[] }) {
  const days = lastDays(7)
  const rows = days.map((d) => ({
    day: d,
    counts: SEVERITIES.map((s) => cases.filter((c) => c.severity === s.id && karachiDay(c.createdAt) === d).length),
  }))
  return (
    <ChartFrame
      title="Cases opened, last 7 days"
      summary="New emergency cases each day, by severity."
      legend={SEVERITIES.map((s) => ({ label: s.label, color: s.color, mark: 'bar' as const }))}
      table={{ columns: ['Day', ...SEVERITIES.map((s) => s.label)], rows: rows.map((r) => [label(r.day), ...r.counts]) }}
      state={rows.some((r) => r.counts.some(Boolean)) ? 'ready' : 'empty'}
      empty="No cases opened in the last 7 days."
    >
      <BarChart
        label="Cases opened per day by severity"
        bars={rows.map((r) => ({
          label: label(r.day),
          segments: SEVERITIES.map((s, i) => ({ key: s.id, label: s.label, value: r.counts[i]!, color: s.color })),
        }))}
      />
    </ChartFrame>
  )
}

// ── Operating rooms ─────────────────────────────────────────────────────────────────────────────────

export function OperatingRoomsCharts() {
  const [schedule, setSchedule] = useState<OperatingRoomSchedule | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let active = true
    getOperatingRoomSchedule(karachiDay(cityNow()))
      .then((s) => active && setSchedule(s))
      .catch(() => active && setFailed(true))
    return () => {
      active = false
    }
  }, [])
  const now = cityNow().getTime()
  const day = karachiDay(now)
  const from = Date.parse(`${day}T08:00:00+05:00`)
  const to = Date.parse(`${day}T20:00:00+05:00`)
  const rooms = schedule?.rooms ?? []
  const bookings = rooms.flatMap((r) => r.bookings)
  const cancelled = bookings.filter((b) => b.status === 'cancelled').length
  const tone = (b: (typeof bookings)[number]) => {
    if (b.status === 'cancelled') return 'cancelled' as const
    const s = Date.parse(b.startsAt)
    const e = Date.parse(b.endsAt)
    return e <= now ? ('done' as const) : s <= now ? ('running' as const) : ('planned' as const)
  }
  return (
    <ChartGrid>
      <ChartFrame
        title="Today’s lists"
        summary={`Each room's bookings today, 08:00 to 20:00, with a line at the time now. ${cancelled} cancelled today.`}
        legend={[
          { label: 'Booked', color: 'var(--chart-1)', mark: 'bar' },
          { label: 'Should be running', color: 'var(--chart-2)', mark: 'bar' },
          { label: 'Done', color: 'color-mix(in srgb, var(--chart-1) 40%, var(--surface))', mark: 'bar' },
        ]}
        table={{
          columns: ['Room', 'Start', 'End', 'Procedure', 'Status'],
          rows: rooms.flatMap((r) =>
            r.bookings.map((b) => [r.name, b.startsAt.slice(11, 16), b.endsAt.slice(11, 16), b.procedure, b.status === 'cancelled' ? 'Cancelled' : tone(b)]),
          ),
        }}
        state={failed ? 'failed' : !schedule ? 'loading' : rooms.length ? 'ready' : 'empty'}
        empty="No rooms registered."
      >
        <Timeline
          label="Today's theatre lists by room"
          from={from}
          to={to}
          now={now}
          rows={rooms.map((r) => ({
            label: r.name,
            items: r.bookings.map((b) => ({
              start: Date.parse(b.startsAt),
              end: Date.parse(b.endsAt),
              label: b.status === 'cancelled' ? `Cancelled: ${b.procedure}` : b.procedure,
              tone: tone(b),
            })),
          }))}
        />
      </ChartFrame>
      <MetricChart
        title="Theatre use, last 7 days"
        summary="Share of rooms in service with a case running, day by day."
        days={7}
        bucket="day"
        lines={[{ label: 'Rooms in use', metric: 'or.in_use', per: 'or.rooms', color: SERIES[0] }]}
      />
    </ChartGrid>
  )
}

// ── Command centre ──────────────────────────────────────────────────────────────────────────────────

export function CommandCentreCharts({ data }: { data: CommandCentre }) {
  const metrics = useMetrics({ metrics: ['beds.occupied', 'beds.in_service', 'er.wait_minutes'], days: 1, perHospital: true })
  const rows = data.hospitals
    .map((h) => {
      const occupied = points(metrics.metrics, `beds.occupied@${h.id}`)
      const total = points(metrics.metrics, `beds.in_service@${h.id}`)
      const byTime = new Map(total.map((p) => [p.t, p.value]))
      const occupancy = occupied.flatMap((p) => (byTime.get(p.t) ? [Math.round((p.value / byTime.get(p.t)!) * 100)] : []))
      const wait = points(metrics.metrics, `er.wait_minutes@${h.id}`)
      // A hospital that keeps no blood (no usable units of any component) isn't short of it.
      const keepsBlood = Object.values(h.components).some((c) => c.usable > 0)
      const critical = keepsBlood ? h.redCells.filter((r) => r.level === 'critical').length : 0
      const now = occupancy[occupancy.length - 1] ?? null
      return { id: h.id, name: h.name, occupancy, now, wait: wait[wait.length - 1]?.value ?? null, critical, escalated: h.cases.escalated }
    })
    // Strain: how full it is and the emergency wait weigh most; critical red-cell groups and escalated cases add.
    .map((r) => ({ ...r, strain: (r.now ?? 0) / 100 + (r.wait ?? 0) / 120 + r.critical * 0.05 + r.escalated * 0.25 }))
    .sort((a, b) => b.strain - a.strain)
  const state = metrics.failed ? 'failed' : metrics.metrics ? 'ready' : 'loading'
  return (
    <ChartFrame
      title="Hospitals by strain"
      summary="Most strained first: bed occupancy over the last 24 hours (the line), the emergency wait, red-cell groups at a critical level (where the hospital keeps blood) and escalated cases."
      table={{
        columns: ['Hospital', 'Beds occupied now', 'Emergency wait (min)', 'Critical red-cell groups', 'Escalated cases'],
        rows: rows.map((r) => [r.name, r.now === null ? '–' : `${r.now}%`, r.wait ?? '–', r.critical, r.escalated]),
      }}
      updatedAt={metrics.metrics ? new Date(metrics.metrics.updatedAt) : null}
      state={state}
    >
      <ol className={styles.strain}>
        {rows.map((r) => (
          <li key={r.id}>
            <span className={styles.strainName}>{r.name}</span>
            <Sparkline values={r.occupancy} max={100} label={`${r.name}: bed occupancy over 24 hours`} />
            <span className={styles.figure}>{r.now === null ? '–' : `${r.now}% full`}</span>
            <span className={styles.figure}>{r.wait === null ? 'no emergency department' : `${Math.round(r.wait)} min wait`}</span>
            <span className={styles.flags}>
              {r.critical > 0 && <span className={styles.flag}>{r.critical} blood {r.critical === 1 ? 'group' : 'groups'} critical</span>}
              {r.escalated > 0 && <span className={styles.flag}>{r.escalated} escalated</span>}
            </span>
          </li>
        ))}
      </ol>
    </ChartFrame>
  )
}

// ── Reports ─────────────────────────────────────────────────────────────────────────────────────────

export function ReportCharts({ report }: { report: Report }) {
  const severities = report.requests.bySeverity
  const fulfilment = report.fulfilment.bySeverity
  return (
    <ChartGrid>
      <ChartFrame
        title="Cases by severity"
        summary="Emergency cases opened in the period, by severity."
        table={{ columns: ['Severity', 'Cases'], rows: severities.map((s) => [s.label, s.count]) }}
      >
        <BarChart
          label="Cases by severity"
          bars={severities.map((s) => ({ label: s.label, segments: [{ key: 'n', label: 'Cases', value: s.count, color: SERIES[0] }] }))}
        />
      </ChartFrame>
      <ChartFrame
        title="Time to fulfil, by severity"
        summary="Median minutes from a case opening to its needs being met."
        table={{ columns: ['Severity', 'Median minutes', 'Cases fulfilled'], rows: fulfilment.map((f) => [f.label, f.medianMinutes ?? '–', f.count]) }}
      >
        <BarChart
          label="Median minutes to fulfil by severity"
          bars={fulfilment.map((f) => ({
            label: f.label,
            segments: [{ key: 'm', label: 'Median minutes', value: f.medianMinutes ?? 0, color: SERIES[1] }],
            note: f.medianMinutes === null ? 'none fulfilled' : `${f.medianMinutes} min`,
          }))}
        />
      </ChartFrame>
    </ChartGrid>
  )
}
