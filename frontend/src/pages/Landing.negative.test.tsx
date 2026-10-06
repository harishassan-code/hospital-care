import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { escapeHtml } from '../auth/login'
import { saveSession } from '../auth/session'
import { staffUser } from '../test/mock-auth'
import { renderWithRouter } from '../test/test-utils'
import Landing, {
  formatResourceCount,
  landingIncludesForeignHospital,
  roleMayAccessCityCommandCenter,
} from './Landing'
import { Route, Routes } from 'react-router-dom'
import ProtectedRoute from '../components/ProtectedRoute'
import Login from './Login'

describe('Main landing page — negative QA', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  afterEach(() => vi.restoreAllMocks())

  it('LAND-N01 redirects unauthenticated users away from the dashboard route', () => {
    renderWithRouter(
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Landing />
            </ProtectedRoute>
          }
        />
      </Routes>,
      { router: { initialEntries: ['/dashboard'] } },
    )
    expect(screen.getByTestId('login-page')).toBeInTheDocument()
    expect(screen.queryByTestId('landing-page')).not.toBeInTheDocument()
  })

  it('LAND-N02 flags API payloads scoped to another hospital', () => {
    expect(
      landingIncludesForeignHospital(
        {
          hospitalId: 'hosp-st-marys',
          hospitalName: "St. Mary's",
          icuBedsAvailable: 1,
          bloodUnitsAvailable: 2,
        },
        'hosp-city-general',
      ),
    ).toBe(true)
  })

  it('LAND-N03 hides city-wide command center from hospital staff', async () => {
    saveSession({ token: 't', user: staffUser }, false)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          hospitalId: staffUser.hospitalId,
          hospitalName: staffUser.hospitalName,
          icuBedsAvailable: 1,
          bloodUnitsAvailable: 2,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    renderWithRouter(<Landing />)
    expect(roleMayAccessCityCommandCenter('hospital_staff')).toBe(false)
    await waitFor(() => expect(screen.getByTestId('landing-page')).toBeInTheDocument())
    expect(screen.queryByText(/city-wide command center/i)).not.toBeInTheDocument()
    expect(screen.queryByTestId('landing-admin-nav')).not.toBeInTheDocument()
  })

  it('LAND-N04 shows per-widget error state when summary API fails', async () => {
    saveSession({ token: 't', user: staffUser }, false)
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network'))
    renderWithRouter(<Landing />)
    expect(await screen.findByTestId('landing-load-error')).toHaveTextContent(/unable to load/i)
  })

  it('LAND-N07 escapes stored XSS in hospital name output', async () => {
    saveSession(
      {
        token: 't',
        user: { ...staffUser, hospitalName: '<img src=x onerror=alert(1)>' },
      },
      false,
    )
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          hospitalId: staffUser.hospitalId,
          hospitalName: '<img src=x onerror=alert(1)>',
          icuBedsAvailable: 0,
          bloodUnitsAvailable: 0,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    renderWithRouter(<Landing />)
    await waitFor(() => expect(screen.getByTestId('landing-hospital-name')).toBeInTheDocument())
    expect(screen.getByTestId('landing-hospital-name').innerHTML).toBe(
      escapeHtml('<img src=x onerror=alert(1)>'),
    )
  })

  it('LAND-N09 renders zero counts as 0 rather than blank or NaN', async () => {
    saveSession({ token: 't', user: staffUser }, false)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          hospitalId: staffUser.hospitalId,
          hospitalName: staffUser.hospitalName,
          icuBedsAvailable: 0,
          bloodUnitsAvailable: 0,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    renderWithRouter(<Landing />)
    expect(await screen.findByTestId('landing-icu-count')).toHaveTextContent('0')
    expect(screen.getByTestId('landing-blood-count')).toHaveTextContent('0')
    expect(formatResourceCount(-3)).toBe('0')
    expect(formatResourceCount(Number.NaN)).toBe('0')
  })

  it('LAND-N06 staff navigation links route to defined paths', async () => {
    saveSession({ token: 't', user: staffUser }, false)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          hospitalId: staffUser.hospitalId,
          hospitalName: staffUser.hospitalName,
          icuBedsAvailable: 1,
          bloodUnitsAvailable: 1,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    renderWithRouter(<Landing />)
    await waitFor(() => expect(screen.getByTestId('landing-staff-nav')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'Blood' })).toHaveAttribute('href', '/blood')
    expect(screen.getByRole('link', { name: 'Beds' })).toHaveAttribute('href', '/beds')
  })

  it('LAND-N08 logout clears session so a return visit has no stored credentials', async () => {
    const user = userEvent.setup()
    saveSession({ token: 't', user: staffUser }, false)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          hospitalId: staffUser.hospitalId,
          hospitalName: staffUser.hospitalName,
          icuBedsAvailable: 1,
          bloodUnitsAvailable: 1,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    renderWithRouter(<Landing />)
    await user.click(await screen.findByTestId('landing-logout'))
    const { loadSession } = await import('../auth/session')
    expect(loadSession()).toBeNull()
  })
})
