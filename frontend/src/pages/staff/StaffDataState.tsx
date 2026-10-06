import { hospital } from '../../config/hospital'
import { useStaff } from '../../features/staff/staffContext'

/** What a staff page shows before its data arrives, or if loading failed. */
export function StaffDataState() {
  const { failed } = useStaff()
  return (
    <p role="status">
      {failed
        ? `The hospital’s system didn’t respond. Reload the page, or call ${hospital.mainPhone} if it keeps happening.`
        : 'Loading…'}
    </p>
  )
}
