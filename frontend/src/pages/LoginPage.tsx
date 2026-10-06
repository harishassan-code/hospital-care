import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { login } from '../api/auth'
import { Button } from '../components/form/Button'
import { FormAlert } from '../components/form/FormAlert'
import { PasswordField } from '../components/form/PasswordField'
import { TextField } from '../components/form/TextField'
import { AuthLayout } from '../components/layout/AuthLayout'
import { safeNext } from '../features/auth/redirect'
import { useAuthForm } from '../features/auth/useAuthForm'
import { validateLogin } from '../features/auth/validation'
import styles from './AuthPages.module.css'

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [helpOpen, setHelpOpen] = useState(false)
  const { values, errors, alert, pending, field, handleSubmit } = useAuthForm({
    initial: { email: '', password: '' },
    validate: validateLogin,
    order: ['email', 'password'],
    onValid: async (v) => {
      const user = await login(v)
      // Staff go to the workspace (or back where they were going); patients to the home page.
      navigate(user.isStaff ? (safeNext(searchParams.get('next')) ?? '/staff') : '/')
    },
  })

  return (
    <AuthLayout
      title="Sign in"
      footer={
        <>
          <p>
            New patient? <Link to="/signup">Create an account</Link>
          </p>
          <p>Hospital staff: use the account your administrator set up for you.</p>
        </>
      }
    >
      <p className={styles.intro}>Patients and hospital staff sign in here.</p>
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <TextField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          value={values.email}
          onChange={field('email')}
          error={errors.email}
        />
        <div className={styles.stack}>
          <PasswordField
            id="password"
            label="Password"
            autoComplete="current-password"
            value={values.password}
            onChange={field('password')}
            error={errors.password}
          />
          <button
            type="button"
            className={styles.textButton}
            aria-expanded={helpOpen}
            aria-controls="password-help"
            onClick={() => setHelpOpen((open) => !open)}
          >
            Forgot your password?
          </button>
          <p id="password-help" className={styles.help} hidden={!helpOpen}>
            Ask the front desk to reset it. Staff: ask your hospital administrator.
          </p>
        </div>
        <FormAlert>{alert}</FormAlert>
        <Button pending={pending} pendingLabel="Logging in…">
          Log in
        </Button>
      </form>
    </AuthLayout>
  )
}
