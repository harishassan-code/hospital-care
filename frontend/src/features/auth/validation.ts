export type FieldErrors<K extends string> = Partial<Record<K, string>>

export type LoginValues = { email: string; password: string }

export type SignupValues = {
  fullName: string
  email: string
  phone: string
  password: string
  confirmPassword: string
  acceptTerms: boolean
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE = /^\+?[\d\s-]{7,20}$/

function emailError(email: string): string | undefined {
  const value = email.trim()
  if (!value) return 'Enter your email address'
  if (!EMAIL.test(value)) return 'Enter an email like name@example.com'
}

function newPasswordError(password: string): string | undefined {
  if (!password) return 'Create a password'
  if (password.length < 8) return 'Use at least 8 characters'
  if (/^\d+$/.test(password)) return 'Use letters as well as numbers'
}

export function validateLogin(values: LoginValues): FieldErrors<keyof LoginValues> {
  const errors: FieldErrors<keyof LoginValues> = {}
  const email = emailError(values.email)
  if (email) errors.email = email
  if (!values.password) errors.password = 'Enter your password'
  return errors
}

export function validateSignup(values: SignupValues): FieldErrors<keyof SignupValues> {
  const errors: FieldErrors<keyof SignupValues> = {}
  if (!values.fullName.trim()) errors.fullName = 'Enter your full name'
  const email = emailError(values.email)
  if (email) errors.email = email
  if (values.phone.trim() && !PHONE.test(values.phone.trim())) {
    errors.phone = 'Enter a phone number using digits, spaces, + or -'
  }
  const password = newPasswordError(values.password)
  if (password) errors.password = password
  if (values.password && !values.confirmPassword) {
    errors.confirmPassword = 'Re-enter your password'
  } else if (values.password && values.confirmPassword !== values.password) {
    errors.confirmPassword = 'Passwords don’t match'
  }
  if (!values.acceptTerms) errors.acceptTerms = 'Agree to the terms to create an account'
  return errors
}

export function firstErrorKey<K extends string>(errors: FieldErrors<K>, order: readonly K[]): K | undefined {
  return order.find((key) => errors[key])
}
