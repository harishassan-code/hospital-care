import { useId, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { INVALID_CREDENTIALS_MESSAGE } from '../auth/constants'
import { authenticateLogin, validateLoginForm } from '../auth/login'
import { getPostLoginPath } from '../auth/roles'
import { saveSession } from '../auth/session'

export default function Login() {
  const formId = useId()
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = (location.state as { from?: string } | null)?.from

  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const canSubmit = Boolean(identifier.trim() && password) && !loading

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const validationErrors = validateLoginForm(identifier, password)
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors)
      return
    }
    setFieldErrors({})
    setLoading(true)
    try {
      const result = await authenticateLogin(identifier, password)
      if (!result.ok) {
        if (result.reason === 'validation') {
          setFieldErrors(result.errors)
        } else {
          setFormError(result.message)
        }
        return
      }
      saveSession({ token: result.token, user: result.user }, rememberMe)
      navigate(getPostLoginPath(result.user, returnTo), { replace: true })
    } catch {
      setFormError(INVALID_CREDENTIALS_MESSAGE)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page" data-testid="login-page" style={{ maxWidth: 420, margin: '0 auto', padding: '48px 16px' }}>
      <div data-testid="login-logo" aria-label="CareLink logo" style={{ fontWeight: 700, fontSize: '1.5rem', marginBottom: 24 }}>
        CareLink
      </div>
      <h1 style={{ fontSize: '1.25rem', marginTop: 0 }}>Sign in</h1>
      <form id={formId} aria-label="Login form" onSubmit={handleSubmit} noValidate>
        <div style={{ marginBottom: 16 }}>
          <label htmlFor={`${formId}-email`}>Email or username</label>
          <input
            id={`${formId}-email`}
            data-testid="login-email"
            name="email"
            type="text"
            autoComplete="username"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            aria-invalid={Boolean(fieldErrors.email)}
            aria-describedby={fieldErrors.email ? `${formId}-email-error` : undefined}
            style={{ display: 'block', width: '100%', marginTop: 4, padding: 8 }}
          />
          {fieldErrors.email ? (
            <p id={`${formId}-email-error`} role="alert" data-testid="login-email-error" style={{ color: 'var(--accent)', margin: '4px 0 0' }}>
              {fieldErrors.email}
            </p>
          ) : null}
        </div>
        <div style={{ marginBottom: 16 }}>
          <label htmlFor={`${formId}-password`}>Password</label>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <input
              id={`${formId}-password`}
              data-testid="login-password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby={fieldErrors.password ? `${formId}-password-error` : undefined}
              style={{ flex: 1, padding: 8 }}
            />
            <button
              type="button"
              tabIndex={-1}
              data-testid="login-toggle-password"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((v) => !v)}
            >
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>
          {fieldErrors.password ? (
            <p id={`${formId}-password-error`} role="alert" data-testid="login-password-error" style={{ color: 'var(--accent)', margin: '4px 0 0' }}>
              {fieldErrors.password}
            </p>
          ) : null}
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              data-testid="login-remember"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
            />
            Remember Me
          </label>
        </div>
        {formError ? (
          <p role="alert" data-testid="login-form-error" style={{ color: 'var(--accent)' }}>
            {formError}
          </p>
        ) : null}
        {loading ? (
          <p role="status" data-testid="login-loading" aria-live="polite">
            Signing in…
          </p>
        ) : null}
        <button type="submit" data-testid="login-submit" disabled={!canSubmit} style={{ marginTop: 8, padding: '8px 16px' }}>
          Login
        </button>
      </form>
      <p style={{ marginTop: 16 }}>
        <Link to="/forgot-password" data-testid="login-forgot-password">
          Forgot Password?
        </Link>
      </p>
    </main>
  )
}
