import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { hospital } from '../config/hospital'
import { samplePublicStatus } from '../test/fixtures/publicStatus'
import { mockApi, ok } from '../test/mockApi'
import LandingPage from './LandingPage'

afterEach(() => vi.restoreAllMocks())

it('shows the hospital, the sign and live emergency status', async () => {
  mockApi({ 'GET /public/status/': ok(samplePublicStatus(new Date())) })
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

it('says so when live status is unavailable', async () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
  render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  )
  expect(await screen.findByText(/Live status isn’t available right now/)).toBeInTheDocument()
})
