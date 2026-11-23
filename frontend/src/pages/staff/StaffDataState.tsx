import { hospital } from '../../config/hospital'
import { useStaff } from '../../features/staff/staffContext'
import styles from './StaffPages.module.css'

/** What a staff page shows before its data arrives, or if loading failed. Pages that load their own data pass `failed`. */
export function StaffDataState({ failed }: { failed?: boolean }) {
  const staff = useStaff()
  const down = failed ?? staff.failed
  return (
    <>
      <p role="status">
        {down
          ? `The hospital’s system didn’t respond. Reload the page, or call ${hospital.mainPhone} if it keeps happening.`
          : 'Loading…'}
      </p>
      {!down && (
        <div className={styles.skeleton} aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      )}
    </>
  )
}
