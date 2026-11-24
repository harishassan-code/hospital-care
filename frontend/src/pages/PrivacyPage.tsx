import { ShieldCheck } from 'lucide-react'
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { SiteFooter } from '../components/layout/SiteFooter'
import { SiteHeader } from '../components/layout/SiteHeader'
import { hospital as site } from '../config/hospital'
import styles from './PrivacyPage.module.css'

/** Each HIPAA safeguard and where CityCare implements it (B23), so the statement at the top can be checked. */
const SAFEGUARDS: { rule: string; cite: string; how: string }[] = [
  {
    rule: 'Minimum necessary',
    cite: 'Privacy Rule, 45 CFR 164.502(b)',
    how: 'Patient details (initials, age, sex, a case’s patient reference and notes, an emergency visit’s details) go only to the doctors, nurses and admin of the patient’s own hospital. Blood bank staff and pharmacists work from a case’s needs. Other hospitals see a case’s needs and status, and who the patient is only once the patient is being moved to them. The CityCare network admin sees counts and statuses, never patients.',
  },
  {
    rule: 'Access control',
    cite: 'Security Rule, 164.312(a)(1)',
    how: 'Everyone signs in with their own account. What each role may open is one table, enforced by the server on every request; staff see their own hospital’s records only.',
  },
  {
    rule: 'Automatic log-off',
    cite: '164.312(a)(2)(iii)',
    how: 'A staff session ends after 30 minutes without use.',
  },
  {
    rule: 'Audit controls',
    cite: '164.312(b)',
    how: 'Every change is recorded: who, what, when and why, before and after. Every time someone is shown patient details, that is recorded too (once per person per page or record every 10 minutes), and so is every export. Admins can search the record; nobody can change it.',
  },
  {
    rule: 'Integrity',
    cite: '164.312(c)(1)',
    how: 'The audit record is append-only, and every status change follows fixed rules, inside a database transaction that locks the record.',
  },
  {
    rule: 'Person authentication',
    cite: '164.312(d)',
    how: 'Passwords with strength rules, limits on sign-in attempts and a lockout after repeated failures.',
  },
  {
    rule: 'Transmission security',
    cite: '164.312(e)(1)',
    how: 'HTTPS only, with HSTS, and secure, HTTP-only cookies.',
  },
  {
    rule: 'De-identified public information',
    cite: '164.514',
    how: 'The public pages show levels and counts only: no patient, no name, no record. Emergency patients are known by a random tag; alerts and page addresses carry case references and tags, never patient details.',
  },
]

/** Patient privacy (B23): the statement, and each safeguard with where it's implemented. */
export default function PrivacyPage() {
  useEffect(() => {
    document.title = `Patient privacy · ${site.name}`
    return () => {
      document.title = site.name
    }
  }, [])
  return (
    <div className={styles.page}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <SiteHeader />
      <main id="main" className={styles.main}>
        <p className={styles.eyebrow}>
          <ShieldCheck size={18} aria-hidden="true" /> Patient privacy
        </p>
        <h1 className={styles.title}>{site.name} is HIPAA compliant.</h1>
        <p className={styles.lead}>
          Patient information reaches only the people who need it for their work, and stays out of everything public.
          Below is each safeguard of the HIPAA Privacy and Security Rules and how {site.name} puts it into practice, so
          you can check it.
        </p>
        <div className="table-scroll">
          <table className={styles.table}>
            <caption className="visually-hidden">HIPAA safeguards and how {site.name} implements them</caption>
            <thead>
              <tr>
                <th scope="col">Safeguard</th>
                <th scope="col">How {site.name} does it</th>
              </tr>
            </thead>
            <tbody>
              {SAFEGUARDS.map((s) => (
                <tr key={s.rule}>
                  <th scope="row">
                    {s.rule}
                    <span className={styles.cite}>{s.cite}</span>
                  </th>
                  <td>{s.how}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className={styles.note}>
          This site is a demonstration. Every patient, donor and staff member on it is made up; never enter real patient
          information. Questions or concerns: contact the {site.name} network office (details below).
        </p>
        <p>
          <Link to="/">Back to the network</Link>
        </p>
      </main>
      <SiteFooter />
    </div>
  )
}
