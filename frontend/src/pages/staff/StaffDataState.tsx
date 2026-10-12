import { hospital } from '../../config/hospital'
import { useStaff } from '../../features/staff/staffContext'

/** What a staff page shows before its data arrives, or if loading failed. Pages that load their own data pass `failed`. */
export function StaffDataState({ failed }: { failed?: boolean }) {
  const staff = useStaff()
  return (
    <p role="status">
      {(failed ?? staff.failed)
        ?`The hospital’s system didn’t respond. Reload the page, or call ${hospital.mainPhone} if it keeps happening.`
        : 'Loading…'}
    </p>
  )
}
