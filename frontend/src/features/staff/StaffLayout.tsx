import { LogOut, Menu } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Logo } from '../../components/brand/Logo'
import { ThemeToggle } from '../../components/ui/ThemeToggle'
import { hospital } from '../../config/hospital'
import { CriticalBanners } from '../notifications/CriticalBanners'
import { CityClockBadge } from '../simulation/CityClockBadge'
import { NotificationBell } from '../notifications/NotificationBell'
import { currentShift, formatDuration } from '../../lib/time'
import { AccessDenied } from './AccessDenied'
import { MODULE_ICONS } from './moduleIcons'
import { PLANNED } from './planned'
import { PURPOSE } from './purposes'
import { canOpen, deniedBecause, moduleForPath, MODULES, ROLES } from './roles'
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
  const { role, user } = useStaff()
  const { pathname } = useLocation()
  const module = moduleForPath(pathname)
  const denied = deniedBecause(role, module.id, Boolean(user.hospital))

  return (
    <div className={styles.shell}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Sidebar />
      <div className={styles.column}>
        <TopBar
          title={PLANNED.find((p) => p.path === pathname.replace(/\/$/, ''))?.label ?? module.label}
          question={isModuleHome(pathname, module.path) ? PURPOSE[module.id] : undefined}
        />
        <div>
          <CriticalBanners />
          <main id="main" className={styles.main}>
            {denied === null ? <Outlet /> : <AccessDenied what={module.label} reason={denied} />}
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
              {MODULES.filter((m) => canOpen(role, m.id, Boolean(user.hospital))).map((m) => {
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

/** The question shows on a module's own page, not on its sub-pages (a case, a hospital's form). */
function isModuleHome(pathname: string, path: string): boolean {
  return pathname.replace(/\/$/, '') === path
}

function TopBar({ title, question }: { title: string; question?: string }) {
  const { now } = useStaff()
  const shift = currentShift(hospital.shifts, now)

  return (
    <header className={styles.topBar}>
      <div className={styles.titleBlock}>
        <h1 className={styles.title}>{title}</h1>
        {question && <p className={styles.question}>{question}</p>}
      </div>
      <div className={styles.topMeta}>
        <CityClockBadge />
        <p className={styles.shift}>
          {`${shift.name} shift · ${shift.start}–${shift.end} · ${formatDuration(shift.minutesLeft)} left`}
        </p>
        <ThemeToggle />
        <NotificationBell />
      </div>
    </header>
  )
}
