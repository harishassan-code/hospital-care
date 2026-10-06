import { useState, type CSSProperties } from 'react'
import type { Doctor } from '../../api/publicStatus'
import styles from './DoctorSchedule.module.css'
import {
  DAY_MINUTES,
  departmentsOf,
  formatClock,
  isInNow,
  minutesOfDay,
  shiftSegments,
  sortForDisplay,
} from './schedule'

const TICK_HOURS = [0, 3, 6, 9, 12, 15, 18, 21, 24]
const ALL = 'All'

const pct = (minutes: number) => `${(minutes / DAY_MINUTES) * 100}%`

type DoctorScheduleProps = {
  doctors: Doctor[]
  now: Date
}

/**
 * Today's doctors on a 24-hour timeline. Every row also states its hours and "In now" in text,
 * so the bars are a visual aid, never the only way to read the schedule.
 */
export function DoctorSchedule({ doctors, now }: DoctorScheduleProps) {
  const [department, setDepartment] = useState(ALL)

  if (doctors.length === 0) {
    return <p>No doctor schedules are published for today.</p>
  }

  const filtered = department === ALL ? doctors : doctors.filter((d) => d.department === department)
  const shown = sortForDisplay(filtered, now)
  const nowAt = pct(minutesOfDay(now))

  return (
    <div className={styles.schedule}>
      <div className={styles.filters} role="group" aria-label="Show doctors from">
        {[ALL, ...departmentsOf(doctors)].map((name) => (
          <button
            key={name}
            type="button"
            className={styles.filter}
            aria-pressed={department === name}
            onClick={() => setDepartment(name)}
          >
            {name}
          </button>
        ))}
      </div>

      <div className={styles.chart}>
        <div className={styles.axis} aria-hidden="true">
          <span className={styles.nowChip} style={{ left: nowAt }}>
            Now {formatClock(now)}
          </span>
          {TICK_HOURS.map((h) => (
            <span key={h} className={styles.tick} style={{ left: pct(h * 60) }}>
              {String(h).padStart(2, '0')}:00
            </span>
          ))}
        </div>

        <div className={styles.plot} aria-hidden="true">
          {TICK_HOURS.map((h) => (
            <span key={h} className={styles.gridline} style={{ left: pct(h * 60) }} />
          ))}
          <span className={styles.nowLine} style={{ left: nowAt }} />
        </div>

        <ul className={styles.list} aria-label="Doctors on duty today">
          {shown.map((doctor) => {
            const inNow = isInNow(doctor, now)
            return (
              <li key={doctor.id} className={styles.row} aria-labelledby={`${doctor.id}-name`} data-in-now={inNow}>
                <div className={styles.who}>
                  <span className={styles.nameLine}>
                    <span id={`${doctor.id}-name`} className={styles.name}>
                      {doctor.name}
                    </span>
                    {inNow && <span className={styles.tag}>In now</span>}
                  </span>
                  <span className={styles.meta}>
                    {doctor.department} · <span className={styles.time}>{`${doctor.start}–${doctor.end}`}</span>
                  </span>
                </div>
                <div className={styles.track} aria-hidden="true">
                  {shiftSegments(doctor.start, doctor.end).map(([from, to]) => (
                    <span
                      key={from}
                      className={styles.bar}
                      data-cut-start={from === 0}
                      data-cut-end={to === DAY_MINUTES}
                      style={{ left: pct(from), width: pct(to - from) } as CSSProperties}
                    />
                  ))}
                </div>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}
