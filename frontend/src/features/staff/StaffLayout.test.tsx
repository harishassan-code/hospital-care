import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { at } from '../../test/clock'
import { mockStaffApi } from '../../test/mockApi'
import StaffLayout from './StaffLayout'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(at('15:00'))
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

function LoginProbe() {
  const { search } = useLocation()
  return <p>login page{search}</p>
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginProbe />} />
        <Route path="/" element={<p>home page</p>} />
        <Route path="/staff" element={<StaffLayout />}>
          <Route index element={<p>overview content</p>} />
          <Route path="beds" element={<p>beds content</p>} />
          <Route path="blood" element={<p>blood content</p>} />
          <Route path="pharmacy" element={<p>pharmacy content</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

const navLinks = () =>
  within(screen.getByRole('navigation', { name: 'Staff' }))
    .getAllByRole('link')
    .map((a) => a.textContent)

const requested = (fetchMock: ReturnType<typeof mockStaffApi>['fetchMock']) =>
  fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname)

describe('StaffLayout', () => {
  it('sends signed-out visitors to the login page and remembers where they were going', async () => {
    mockStaffApi({ role: null })
    renderAt('/staff/beds')
    expect(await screen.findByText('login page?next=%2Fstaff%2Fbeds')).toBeInTheDocument()
  })

  it('tells patients the workspace is for hospital staff', async () => {
    mockStaffApi({ role: 'patient' })
    renderAt('/staff')
    expect(await screen.findByRole('heading', { name: 'This area is for hospital staff' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /home page/i })).toHaveAttribute('href', '/')
  })

  it('shows an admin every module, their name, and the current page', async () => {
    mockStaffApi({ role: 'admin' })
    renderAt('/staff/beds')
    expect(await screen.findByText('beds content')).toBeInTheDocument()
    expect(navLinks()).toEqual(['Overview', 'Beds', 'Blood bank', 'Pharmacy'])
    expect(screen.getByRole('link', { name: 'Beds' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('Sadia Admin')).toBeInTheDocument()
  })

  it('only shows and loads the modules a role may use', async () => {
    const { fetchMock } = mockStaffApi({ role: 'pharmacist' })
    renderAt('/staff')
    expect(await screen.findByText('overview content')).toBeInTheDocument()
    expect(navLinks()).toEqual(['Overview', 'Pharmacy'])
    expect(requested(fetchMock)).toContain('/api/pharmacy/stock/')
    expect(requested(fetchMock)).not.toContain('/api/beds/')
    expect(requested(fetchMock)).not.toContain('/api/blood/units/')
  })

  it('blocks a page the role cannot open', async () => {
    mockStaffApi({ role: 'nurse' })
    renderAt('/staff/blood')
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
    expect(screen.queryByText('blood content')).toBeNull()
  })

  it('explains when the hospital system cannot be reached', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    renderAt('/staff')
    expect(await screen.findByText(/hospital’s system didn’t respond/)).toBeInTheDocument()
  })

  it('signs out through the API and returns to the login page', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderAt('/staff')
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))
    expect(await screen.findByText('login page')).toBeInTheDocument()
    expect(requested(fetchMock)).toContain('/api/auth/logout/')
  })

  it('shows the current shift and how many items need attention', async () => {
    mockStaffApi({ role: 'admin' })
    renderAt('/staff')
    expect(await screen.findByText(/Evening shift/)).toHaveTextContent('Evening shift · 14:00–20:00 · 5 h left')
    const bell = await screen.findByRole('link', { name: /items? need attention/ })
    expect(bell).toHaveAttribute('href', '/staff#attention')
  })
})
