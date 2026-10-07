/**
 * QA cases for the public home page (companion to TC-01 entry flow).
 * Degrades gracefully when live status cannot be loaded (similar intent to LAND-N04).
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { hospital } from '../config/hospital'
import { samplePublicStatus } from '../test/fixtures/publicStatus'
import { mockApi, ok } from '../test/mockApi'
import LandingPage from '../pages/LandingPage'

afterEach(() => vi.restoreAllMocks())

describe('Public home (TC-01 / PUB)', () => {
  it('PUB-01 TC-01 the public home shows hospital branding, wayfinding, and sign-in', async () => {
    mockApi({ 'GET /public/status/': ok(samplePublicStatus(new Date())) })
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Where do you need to go?' })).toBeInTheDocument()
    expect(screen.getAllByText(hospital.name).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Log in' })[0]).toHaveAttribute('href', '/login')
    expect((await screen.findAllByText(/min wait/)).length).toBeGreaterThan(0)
  })

  it('PUB-02 LAND-N04 (ADAPTED) live ER status failure shows a clear message, not a blank page', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Live status isn’t available right now/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Where do you need to go?' })).toBeInTheDocument()
  })
})
