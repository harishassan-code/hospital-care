import { ButtonLink } from '../../components/form/Button'
import styles from './SignInOptions.module.css'

export function SignInOptions() {
  return (
    <div className={styles.options}>
      <article className={styles.option}>
        <h3 className={styles.title}>Patients and visitors</h3>
        <p>New here? Create a patient account. Already registered? Log in with your email.</p>
        <div className={styles.actions}>
          <ButtonLink to="/signup">Create account</ButtonLink>
          <ButtonLink to="/login" variant="secondary">
            Log in
          </ButtonLink>
        </div>
      </article>
      <article className={styles.option}>
        <h3 className={styles.title}>Hospital staff</h3>
        <p>Manage beds, stock and patient care. Your account is set up by your hospital administrator.</p>
        <div className={styles.actions}>
          <ButtonLink to="/login" variant="secondary">
            Staff log in
          </ButtonLink>
        </div>
      </article>
    </div>
  )
}
