/**
 * The seeded demo logins from README "Signing in". Every name and account is synthetic, and the password is the one
 * the README publishes. `seed_demo` creates them (backend/apps/core/management/commands/seed_demo.py).
 */
export const DEMO_PASSWORD = 'CityCare-demo-1'

export const ACCOUNTS = {
  admin: 'admin@demo.citycare.pk',
  doctor: 'doctor@demo.citycare.pk',
  nurse: 'nurse@demo.citycare.pk',
  bloodBank: 'bloodbank@demo.citycare.pk',
  pharmacist: 'pharmacist@demo.citycare.pk',
  patient: 'patient@demo.citycare.pk',
} as const

export type Role = keyof typeof ACCOUNTS
