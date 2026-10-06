import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expect, it } from 'vitest'
import { PasswordField } from './PasswordField'

function Harness() {
  const [value, setValue] = useState('')
  return (
    <PasswordField
      id="pw"
      label="Password"
      value={value}
      onChange={setValue}
      autoComplete="current-password"
      error="Enter your password"
    />
  )
}

it('toggles visibility and links the error to the input', async () => {
  render(<Harness />)
  const input = screen.getByLabelText('Password')
  expect(input).toHaveAttribute('type', 'password')
  expect(input).toHaveAttribute('aria-invalid', 'true')
  expect(input).toHaveAccessibleDescription('Enter your password')

  await userEvent.click(screen.getByRole('button', { name: 'Show password' }))
  expect(input).toHaveAttribute('type', 'text')
  expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true')
})
