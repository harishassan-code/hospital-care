import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, it } from 'vitest'
import { hospital } from '../config/hospital'
import LandingPage from './LandingPage'

it('shows the hospital, the sign and live emergency status', async () => {
  render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  )
  expect(screen.getAllByText(hospital.name).length).toBeGreaterThan(0)
  expect(screen.getByRole('heading', { level: 1, name: 'Where do you need to go?' })).toBeInTheDocument()

  const sign = screen.getByRole('navigation', { name: 'On this page' })
  const hrefs = Array.from(sign.querySelectorAll('a')).map((a) => a.getAttribute('href'))
  expect(hrefs).toEqual(['#emergency', '#doctors', '#sign-in'])

  expect((await screen.findAllByText(/min wait/)).length).toBeGreaterThan(0)
  expect(screen.getByRole('link', { name: `Emergency: ${hospital.emergencyNumber}` })).toHaveAttribute(
    'href',
    `tel:${hospital.emergencyNumber}`,
  )
})
