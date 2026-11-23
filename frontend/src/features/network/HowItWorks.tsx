import { Building2, HeartPulse, Stethoscope } from 'lucide-react'
import styles from './Network.module.css'

const AUDIENCES = [
  {
    icon: HeartPulse,
    title: 'For patients',
    points: [
      'See which emergency departments are open and how long the wait is, across the city.',
      'Find the hospital that offers what you need, and who is on duty there.',
      'In an emergency the hospitals find the blood, bed or theatre for you, even at another hospital.',
    ],
  },
  {
    icon: Building2,
    title: 'For hospitals',
    points: [
      'Share and borrow blood, beds, equipment, operating rooms and ambulances with the rest of the network.',
      'Requests are matched to the best source, held, and tracked to delivery.',
      'A city command centre sees every hospital’s strain at once and spots shortages early.',
    ],
  },
  {
    icon: Stethoscope,
    title: 'For staff',
    points: [
      'One workspace for beds, blood, cases, transfers and alerts, at your hospital.',
      'Each role sees what its work needs, and every change is recorded.',
      'Patient details stay with the staff treating the patient.',
    ],
  },
] as const

/** What CityCare does, for each audience (B19). */
export function HowItWorks() {
  return (
    <ul className={styles.audiences}>
      {AUDIENCES.map(({ icon: Icon, title, points }) => (
        <li key={title} className={styles.audience}>
          <span className={styles.audienceIcon} aria-hidden="true">
            <Icon size={22} />
          </span>
          <h3 className={styles.audienceTitle}>{title}</h3>
          <ul className={styles.points}>
            {points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  )
}
