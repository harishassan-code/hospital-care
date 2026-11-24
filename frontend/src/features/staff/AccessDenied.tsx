import { Link } from 'react-router-dom'
import { ROLES } from './roles'
import { useStaff } from './staffContext'
import styles from './StaffLayout.module.css'

/** Shown instead of a page the role can't open. The API refuses the same thing with 403. */
export function AccessDenied({ what, reason = 'role' }: { what: string; reason?: 'role' | 'network' | 'hospital' }) {
  const { role } = useStaff()
  const roleLabel = ROLES.find((r) => r.id === role)?.label
  return (
    <div className={styles.denied}>
      <h2>You don’t have access to this page</h2>
      {reason === 'network' ? (
        <p>Only the CityCare admin, who works for the whole network rather than one hospital, can open {what}.</p>
      ) : reason === 'hospital' ? (
        <p>{what} is about one hospital’s own floor, and your account works for the whole network, not one hospital.</p>
      ) : (
        <p>
          The {roleLabel} role can’t open {what}. Ask an administrator if you need it for your work.
        </p>
      )}
      <Link to="/staff">Go to Overview</Link>
    </div>
  )
}
