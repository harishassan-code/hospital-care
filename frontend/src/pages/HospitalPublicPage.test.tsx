import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { samplePublicHospitalDetail } from '../test/fixtures/publicNetwork'
import { fail, mockApi, ok } from '../test/mockApi'
import HospitalPublicPage from './HospitalPublicPage'

afterEach(() => vi.restoreAllMocks())

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/hospitals/:id" element={<HospitalPublicPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

it('shows one hospital: emergency department, who is on duty, beds and departments', async () => {
  mockApi({ 'GET /auth/me/': fail(403), 'GET /public/hospitals/2/': ok(samplePublicHospitalDetail(new Date(), 2)) })
  renderAt('/hospitals/2')
  expect(await screen.findByRole('heading', { level: 1, name: 'Seaview Hospital' })).toBeInTheDocument()
  const er = screen.getByRole('region', { name: 'Emergency department' })
  expect(within(er).getByText('Very busy')).toBeInTheDocument()
  expect(within(er).getByText('Estimated wait').nextSibling).toHaveTextContent('75 min')
  const duty = screen.getByRole('region', { name: 'On duty now' })
  expect(within(duty).getByText('Cardiology').closest('li')).toHaveTextContent('2 doctors')
  expect(within(duty).getByText('Doctors’ names are shown to signed-in hospital staff.')).toBeInTheDocument()
  expect(within(duty).queryByText(/Ayesha/)).not.toBeInTheDocument()
  expect(within(screen.getByRole('region', { name: 'Beds' })).getByText('ICU').closest('li')).toHaveTextContent('Limited')
  expect(within(screen.getByRole('region', { name: 'Services and departments' })).getByText('Cardiology')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /All hospitals/ })).toHaveAttribute('href', '/#hospitals')
})

it('shows names to signed-in staff, as the server sends them', async () => {
  mockApi({ 'GET /auth/me/': fail(403), 'GET /public/hospitals/2/': ok(samplePublicHospitalDetail(new Date(), 2, true)) })
  renderAt('/hospitals/2')
  const duty = await screen.findByRole('region', { name: 'On duty now' })
  expect(within(duty).getByText('Dr. Ayesha Khan, Dr. Omar Sheikh')).toBeInTheDocument()
  expect(within(duty).queryByText(/shown to signed-in hospital staff/)).not.toBeInTheDocument()
})

it('says when a hospital is not in the network', async () => {
  mockApi({ 'GET /auth/me/': fail(403), 'GET /public/hospitals/99/': fail(404, { detail: 'Not found.' }) })
  renderAt('/hospitals/99')
  expect(await screen.findByRole('heading', { name: 'We couldn’t find that hospital' })).toBeInTheDocument()
})

it('says when the page is unavailable', async () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
  renderAt('/hospitals/2')
  expect(await screen.findByText('This hospital’s page isn’t available right now.')).toBeInTheDocument()
})
