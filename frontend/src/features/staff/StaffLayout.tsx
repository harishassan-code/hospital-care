import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { hospital } from '../../config/hospital'
import { currentShift, formatDuration } from '../../lib/time'
import { AccessDenied } from './AccessDenied'
import { PLANNED } from './planned'
import { canSee, moduleForPath, MODULES, ROLES } from './roles'
import { useStaff } from './staffContext'
import { useNotifications } from './useNotifications'
import styles from './StaffLayout.module.css'
import { StaffProvider } from './StaffProvider'

/** The signed-in staff workspace: sidebar, top bar, and the current page. */
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
  const module = moduleForPath(pathname)
  const notifications = useNotifications()

  return (
    <div className={styles.shell}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Sidebar />
      <div className={styles.column}>
        <TopBar
          title={PLANNED.find((p) => p.path === pathname.replace(/\/$/, ''))?.label ?? module.label}
          unread={notifications.unread}
        />
        {notifications.critical.map((n) => (
          <div key={n.id} role="alert" className={styles.banner}>
            <span>
              <strong>{n.title}</strong> {n.body}
              {n.link && (
                <>
                  {' '}
                  <Link to={n.link}>Open</Link>
                </>
              )}
            </span>
            <button type="button" className={styles.signOut} onClick={() => notifications.acknowledge(n.id)}>
              Acknowledge
            </button>
          </div>
        ))}
        <main id="main" className={styles.main}>
          {canSee(role, module.id) ? <Outlet /> : <AccessDenied what={module.label} />}
        </main>
      </div>
    </div>
  )
}

function Sidebar() {
  const { user, role, signOut } = useStaff()
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
            <p className={styles.userName}>{user.fullName}</p>
            <p className={styles.userRole}>{roleLabel}</p>
            {user.hospital && <p className={styles.userRole}>{user.hospital.name}</p>}
            <button type="button" className={styles.signOut} onClick={signOut}>
              Sign out
            </button>
          </div>
        </div>
      </div>
    </aside>
  )
}

function TopBar({ title, unread }: { title: string; unread: number }) {
  const { now, attention } = useStaff()
  const shift = currentShift(hospital.shifts, now)
  // One badge: server notifications (story #53) plus the items worked out in the browser.
  const count = attention.length + unread

  return (
    <header className={styles.topBar}>
      <h1 className={styles.title}>{title}</h1>
      <div className={styles.topMeta}>
        <p className={styles.shift}>
          {`${shift.name} shift · ${shift.start}–${shift.end} · ${formatDuration(shift.minutesLeft)} left`}
        </p>
        <Link
          to={unread > 0 ? '/staff/alerts' : { pathname: '/staff', hash: 'attention' }}
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
