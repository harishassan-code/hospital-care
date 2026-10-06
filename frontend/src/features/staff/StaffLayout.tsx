import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { hospital } from '../../config/hospital'
import { currentShift, formatDuration } from '../../lib/time'
import { canSee, MODULES, ROLES, type Role } from './roles'
import { useStaff } from './staffContext'
import styles from './StaffLayout.module.css'
import { StaffProvider } from './StaffProvider'

/** The signed-in staff workspace: sidebar, top bar, preview banner, and the current page. */
export default function StaffLayout() {
  return (
    <StaffProvider>
      <StaffShell />
    </StaffProvider>
  )
}

function StaffShell() {
  const { role } = useStaff()
  const { pathname } = useLocation()
  const module = MODULES.find((m) => m.path === pathname.replace(/\/$/, '')) ?? MODULES[0]

  return (
    <div className={styles.shell}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Sidebar />
      <div className={styles.column}>
        <PreviewBanner />
        <TopBar title={module.label} />
        <main id="main" className={styles.main}>
          {canSee(role, module.id) ? <Outlet /> : <AccessDenied moduleLabel={module.label} />}
        </main>
      </div>
    </div>
  )
}

function Sidebar() {
  const { role } = useStaff()
  const [open, setOpen] = useState(false)
  const roleLabel = ROLES.find((r) => r.id === role)?.label

  return (
    <aside className={styles.sidebar}>
      <div className={styles.sidebarInner}>
        <div className={styles.brandRow}>
          <Link to="/staff" className={styles.brand}>
            <span className={styles.monogram} aria-hidden="true">
              {hospital.monogram}
            </span>
            <span>
              <span className={styles.brandName}>{hospital.shortName}</span>
              <span className={styles.brandSub}>Staff workspace</span>
            </span>
          </Link>
          <button
            type="button"
            className={styles.menuButton}
            aria-expanded={open}
            aria-controls="staff-nav"
            onClick={() => setOpen((o) => !o)}
          >
            Menu
          </button>
        </div>
        <div id="staff-nav" className={styles.navArea} data-open={open}>
          <nav aria-label="Staff">
            <ul className={styles.navList}>
              {MODULES.filter((m) => canSee(role, m.id)).map((m) => (
                <li key={m.id}>
                  <NavLink to={m.path} end className={styles.navLink} onClick={() => setOpen(false)}>
                    {m.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <div className={styles.user}>
            <p className={styles.userName}>Preview user</p>
            <p className={styles.userRole}>{roleLabel}</p>
            <Link to="/login" className={styles.signOut}>
              Sign out
            </Link>
          </div>
        </div>
      </div>
    </aside>
  )
}

function PreviewBanner() {
  const { role, setRole } = useStaff()
  return (
    <div className={styles.banner}>
      <p>
        <strong>Preview:</strong> sign-in isn’t connected yet, so pick a role to see what it can do.
      </p>
      <label className={styles.roleField}>
        Viewing as
        <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
          {ROLES.map((r) => (
            <option key={r.id} value={r.id}>
              {r.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}

function TopBar({ title }: { title: string }) {
  const { now, attention } = useStaff()
  const shift = currentShift(hospital.shifts, now)
  const count = attention.length

  return (
    <header className={styles.topBar}>
      <h1 className={styles.title}>{title}</h1>
      <div className={styles.topMeta}>
        <p className={styles.shift}>
          {`${shift.name} shift · ${shift.start}–${shift.end} · ${formatDuration(shift.minutesLeft)} left`}
        </p>
        <Link
          to={{ pathname: '/staff', hash: 'attention' }}
          className={styles.bell}
          aria-label={`${count} ${count === 1 ? 'item needs' : 'items need'} attention`}
        >
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path d="M12 3a6 6 0 0 0-6 6v4l-2 3h16l-2-3V9a6 6 0 0 0-6-6Zm-2.5 15a2.5 2.5 0 0 0 5 0" fill="none" stroke="currentColor" strokeWidth="2" />
          </svg>
          {count > 0 && <span className={styles.bellCount}>{count}</span>}
        </Link>
      </div>
    </header>
  )
}

function AccessDenied({ moduleLabel }: { moduleLabel: string }) {
  const { role } = useStaff()
  const roleLabel = ROLES.find((r) => r.id === role)?.label
  return (
    <div className={styles.denied}>
      <h2>You don’t have access to this page</h2>
      <p>
        The {roleLabel} role can’t open {moduleLabel}. Ask an administrator if you need it for your work.
      </p>
      <Link to="/staff">Go to Overview</Link>
    </div>
  )
}
