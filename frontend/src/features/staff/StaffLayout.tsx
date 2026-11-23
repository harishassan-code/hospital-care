import { LogOut, Menu } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Logo } from '../../components/brand/Logo'
import { hospital } from '../../config/hospital'
import { CriticalBanners } from '../notifications/CriticalBanners'
import { NotificationBell } from '../notifications/NotificationBell'
import { currentShift, formatDuration } from '../../lib/time'
import { AccessDenied } from './AccessDenied'
import { MODULE_ICONS } from './moduleIcons'
import { PLANNED } from './planned'
import { canSee, moduleForPath, MODULES, ROLES } from './roles'
import { useStaff } from './staffContext'
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

  return (
    <div className={styles.shell}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Sidebar />
      <div className={styles.column}>
        <TopBar title={PLANNED.find((p) => p.path === pathname.replace(/\/$/, ''))?.label ?? module.label} />
        <div>
          <CriticalBanners />
          <main id="main" className={styles.main}>
            {canSee(role, module.id) ? <Outlet /> : <AccessDenied what={module.label} />}
          </main>
        </div>
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
            <Logo className={styles.logo} />
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
            <Menu size={18} aria-hidden="true" />
            Menu
          </button>
        </div>
        <div id="staff-nav" className={styles.navArea} data-open={open}>
          <nav aria-label="Staff">
            <ul className={styles.navList}>
              {MODULES.filter((m) => canSee(role, m.id)).map((m) => {
                const Icon = MODULE_ICONS[m.id]
                return (
                  <li key={m.id}>
                    <NavLink to={m.path} end className={styles.navLink} onClick={() => setOpen(false)}>
                      {Icon && <Icon className={styles.navIcon} size={18} strokeWidth={2} aria-hidden="true" />}
                      {m.label}
                    </NavLink>
                  </li>
                )
              })}
            </ul>
          </nav>
          <div className={styles.user}>
            <p className={styles.userName}>{user.fullName}</p>
            <p className={styles.userRole}>{roleLabel}</p>
            {user.hospital && <p className={styles.userRole}>{user.hospital.name}</p>}
            <button type="button" className={styles.signOut} onClick={signOut}>
              <LogOut size={16} aria-hidden="true" />
              Sign out
            </button>
          </div>
        </div>
      </div>
    </aside>
  )
}

function TopBar({ title }: { title: string }) {
  const { now } = useStaff()
  const shift = currentShift(hospital.shifts, now)

  return (
    <header className={styles.topBar}>
      <h1 className={styles.title}>{title}</h1>
      <div className={styles.topMeta}>
        <p className={styles.shift}>
          {`${shift.name} shift · ${shift.start}–${shift.end} · ${formatDuration(shift.minutesLeft)} left`}
        </p>
        <NotificationBell />
      </div>
    </header>
  )
}
