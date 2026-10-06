import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { signup } from '../api/auth'
import { Button, ButtonLink } from '../components/form/Button'
import { Checkbox } from '../components/form/Checkbox'
import { FormAlert } from '../components/form/FormAlert'
import { PasswordField } from '../components/form/PasswordField'
import { TextField } from '../components/form/TextField'
import { AuthLayout } from '../components/layout/AuthLayout'
import { hospital } from '../config/hospital'
import { useAuthForm } from '../features/auth/useAuthForm'
import { validateSignup, type SignupValues } from '../features/auth/validation'
import styles from './AuthPages.module.css'

const EMPTY: SignupValues = {
  fullName: '',
  email: '',
  phone: '',
  password: '',
  confirmPassword: '',
  acceptTerms: false,
}

export default function SignupPage() {
  const [created, setCreated] = useState(false)
  const successHeading = useRef<HTMLHeadingElement>(null)
  const { values, errors, alert, pending, field, handleSubmit } = useAuthForm({
    initial: EMPTY,
    validate: validateSignup,
    order: ['fullName', 'email', 'phone', 'password', 'confirmPassword', 'acceptTerms'],
    onValid: async (v) => {
      await signup(v)
      setCreated(true)
    },
  })

  useEffect(() => {
    if (created) successHeading.current?.focus()
  }, [created])

  if (created) {
    return (
      <AuthLayout title="Create a patient account">
        <div className={styles.success}>
          <h2 ref={successHeading} tabIndex={-1} className={styles.successTitle}>
            Account created. You can now log in.
          </h2>
          <p>Use {values.email.trim()} and the password you just chose.</p>
          <ButtonLink to="/login">Log in</ButtonLink>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Create a patient account"
      footer={
        <p>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      }
    >
      <p className={styles.notice}>
        Work here? Your administrator creates staff accounts. <Link to="/login">Log in instead</Link>.
      </p>
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <TextField
          id="fullName"
          label="Full name"
          autoComplete="name"
          value={values.fullName}
          onChange={field('fullName')}
          error={errors.fullName}
        />
        <TextField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          value={values.email}
          onChange={field('email')}
          error={errors.email}
        />
        <TextField
          id="phone"
          label="Phone"
          type="tel"
          autoComplete="tel"
          optional
          value={values.phone}
          onChange={field('phone')}
          error={errors.phone}
        />
        <PasswordField
          id="password"
          label="Password"
          autoComplete="new-password"
          hint="At least 8 characters, not only numbers"
          value={values.password}
          onChange={field('password')}
          error={errors.password}
        />
        <PasswordField
          id="confirmPassword"
          label="Confirm password"
          autoComplete="new-password"
          value={values.confirmPassword}
          onChange={field('confirmPassword')}
          error={errors.confirmPassword}
        />
        <Checkbox
          id="acceptTerms"
          checked={values.acceptTerms}
          onChange={field('acceptTerms')}
          error={errors.acceptTerms}
        >
          I agree to {hospital.name}’s terms of use and privacy notice
        </Checkbox>
        <FormAlert>{alert}</FormAlert>
        <Button pending={pending} pendingLabel="Creating account…">
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}
