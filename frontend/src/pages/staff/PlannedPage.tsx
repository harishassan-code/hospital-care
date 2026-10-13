import { Link, useLocation } from 'react-router-dom'
import { Panel } from '../../components/ui/Panel'
import { PLANNED } from '../../features/staff/planned'
import pageStyles from './StaffPages.module.css'

/** Placeholder for an MVP module that arrives in a later sprint. */
export default function PlannedPage() {
  const { pathname } = useLocation()
  const planned = PLANNED.find((p) => p.path === pathname.replace(/\/$/, ''))
  if (!planned) return null
  return (
    <Panel title={`${planned.label}: coming in Sprint ${planned.sprint}`}>
      <p>
        This part of Hospital Care isn’t built yet. It’s planned for Sprint {planned.sprint} (backlog {planned.issues}).
      </p>
      <p className={pageStyles.note}>
        <Link to="/staff">Go to Overview</Link>
      </p>
    </Panel>
  )
}
