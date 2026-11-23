import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { hospital } from '../config/hospital'
import { sampleNetwork, samplePublicHospitals } from '../test/fixtures/publicNetwork'
import { mockApi, ok } from '../test/mockApi'
import LandingPage from './LandingPage'

afterEach(() => vi.restoreAllMocks())

function renderHome() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  )
}

function mockNetwork() {
  const now = new Date()
  mockApi({ 'GET /public/network/': ok(sampleNetwork(now)), 'GET /public/hospitals/': ok(samplePublicHospitals(now)) })
}

it('presents the network, not one hospital', async () => {
  mockNetwork()
  renderHome()
  expect(screen.getByRole('heading', { level: 1, name: 'Every hospital in the city, working as one.' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: `How ${hospital.name} works` })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Find a hospital' })).toHaveAttribute('href', '#hospitals')
  // No doctor rota or department timetable on the home page (B19).
  expect(await screen.findByRole('heading', { name: 'Hospitals in the network' })).toBeInTheDocument()
  expect(screen.queryByText(/Dr\./)).not.toBeInTheDocument()
  expect(screen.queryByText(/on duty today/i)).not.toBeInTheDocument()
})

it('shows the city right now', async () => {
  mockNetwork()
  renderHome()
  const stats = await screen.findByRole('list', { name: 'The network right now' })
  expect(within(stats).getByText('hospitals in the network')).toBeInTheDocument()
  expect(within(stats).getByText(/1 very busy · 1 not accepting ambulances/)).toBeInTheDocument()
  expect(within(stats).getByRole('link', { name: 'CityCare General Hospital' })).toHaveAttribute('href', '/hospitals/1')
  expect(within(stats).getByText('ambulances free to respond')).toBeInTheDocument()
  const beds = screen.getByRole('region', { name: 'Beds across the city' })
  expect(within(beds).getByText('NICU').closest('li')).toHaveTextContent('Full')
  const blood = screen.getByRole('region', { name: 'Blood supply' })
  expect(within(blood).getByText('A-').closest('li')).toHaveTextContent('Critical')
})

it('lists the hospitals, shortest wait first, diverting and unreported last', async () => {
  mockNetwork()
  renderHome()
  const directory = await screen.findByRole('region', { name: 'Hospitals in the network' })
  const names = within(directory)
    .getAllByRole('heading', { level: 3 })
    .map((h) => h.textContent)
  expect(names).toEqual([
    'CityCare General Hospital',
    'Seaview Hospital',
    'Northside Children’s Hospital',
    'Karachi Regional Blood Centre',
  ])
  expect(within(directory).getByRole('link', { name: 'Seaview Hospital' })).toHaveAttribute('href', '/hospitals/2')
  const bloodCentre = within(directory).getByRole('heading', { name: 'Karachi Regional Blood Centre' }).closest('li') as HTMLElement
  expect(within(bloodCentre).getByText('Blood bank')).toBeInTheDocument()
})

it('sorts by distance when the visitor shares their location, and keeps it on the device', async () => {
  mockNetwork()
  const getCurrentPosition = vi.fn((success: PositionCallback) =>
    success({ coords: { latitude: 24.94, longitude: 67.03 } } as GeolocationPosition),
  )
  vi.stubGlobal('navigator', { ...navigator, geolocation: { getCurrentPosition } })
  renderHome()
  const directory = await screen.findByRole('region', { name: 'Hospitals in the network' })
  within(directory).getByRole('button', { name: 'Use my location' }).click()
  expect(await within(directory).findByText(/Nearest first\. Your location stays on this device\./)).toBeInTheDocument()
  const first = within(directory).getAllByRole('heading', { level: 3 })[0]
  expect(first).toHaveTextContent('Northside Children’s Hospital')
  // Only the two public reads went to the server: the location never did.
  const calls = vi.mocked(globalThis.fetch).mock.calls.map(([url]) => String(url))
  expect(calls.every((url) => !url.includes('24.94'))).toBe(true)
  vi.unstubAllGlobals()
})

it('says so when the live figures are unavailable', async () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
  renderHome()
  expect(await screen.findByText(/Live status isn’t available right now/)).toBeInTheDocument()
  expect(await screen.findByText(/The hospital list isn’t available right now/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: `Emergency: ${hospital.emergencyNumber}` })).toHaveAttribute(
    'href',
    `tel:${hospital.emergencyNumber}`,
  )
})
