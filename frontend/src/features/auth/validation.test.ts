import { describe, expect, it } from 'vitest'
import { firstErrorKey, validateLogin, validateSignup, type SignupValues } from './validation'

const validSignup: SignupValues = {
  fullName: 'Sara Ahmed',
  email: 'sara@example.com',
  phone: '',
  password: 'blood-bank-7',
  confirmPassword: 'blood-bank-7',
  acceptTerms: true,
}

describe('validateLogin', () => {
  it('requires email and password', () => {
    expect(validateLogin({ email: '', password: '' })).toEqual({
      email: 'Enter your email address',
      password: 'Enter your password',
    })
  })

  it('rejects a malformed email', () => {
    expect(validateLogin({ email: 'sara@', password: 'x' }).email).toBe('Enter an email like name@example.com')
  })

  it('accepts valid input, ignoring surrounding spaces in the email', () => {
    expect(validateLogin({ email: ' sara@example.com ', password: 'x' })).toEqual({})
  })
})

describe('validateSignup', () => {
  it('accepts a valid form', () => {
    expect(validateSignup(validSignup)).toEqual({})
  })

  it('requires a name', () => {
    expect(validateSignup({ ...validSignup, fullName: '  ' }).fullName).toBe('Enter your full name')
  })

  it('requires a password', () => {
    expect(validateSignup({ ...validSignup, password: '', confirmPassword: '' }).password).toBe('Create a password')
  })

  it('needs at least 8 characters', () => {
    expect(validateSignup({ ...validSignup, password: 'abc1', confirmPassword: 'abc1' }).password).toBe(
      'Use at least 8 characters',
    )
  })

  it('rejects passwords made only of digits', () => {
    expect(validateSignup({ ...validSignup, password: '12345678', confirmPassword: '12345678' }).password).toBe(
      'Use letters as well as numbers',
    )
  })

  it('asks for the confirmation when it is left empty', () => {
    expect(validateSignup({ ...validSignup, confirmPassword: '' }).confirmPassword).toBe('Re-enter your password')
  })

  it('checks the confirmation matches', () => {
    expect(validateSignup({ ...validSignup, confirmPassword: 'other-pass-1' }).confirmPassword).toBe(
      'Passwords don’t match',
    )
  })

  it('treats phone as optional but checks its format when given', () => {
    expect(validateSignup({ ...validSignup, phone: '+92 300-1234567' }).phone).toBeUndefined()
    expect(validateSignup({ ...validSignup, phone: 'call me' }).phone).toBe(
      'Enter a phone number using digits, spaces, + or -',
    )
  })

  it('requires agreeing to the terms', () => {
    expect(validateSignup({ ...validSignup, acceptTerms: false }).acceptTerms).toBe(
      'Agree to the terms to create an account',
    )
  })
})

describe('firstErrorKey', () => {
  it('returns the first invalid field in form order', () => {
    expect(firstErrorKey({ password: 'x', email: 'y' }, ['email', 'password'] as const)).toBe('email')
  })

  it('returns undefined when there are no errors', () => {
    expect(firstErrorKey({}, ['email', 'password'] as const)).toBeUndefined()
  })
})
