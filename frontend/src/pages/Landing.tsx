import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { API_URL } from '../api/client'
import { escapeHtml } from '../auth/login'
import type { UserRole } from '../auth/roles'
import { clearSession, getAuthHeaders, loadSession } from '../auth/session'

export type ResourceSummary = {
  hospitalId: string
  hospitalName: string
  icuBedsAvailable: number
  bloodUnitsAvailable: number
}

type LoadState = 'loading' | 'ready' | 'error'

export function formatResourceCount(value: number): string {
  if (!Number.isFinite(value) || value < 0) return '0'
  return String(value)
}

export function landingIncludesForeignHospital(
  summary: ResourceSummary,
  sessionHospitalId: string | null,
): boolean {
  if (!sessionHospitalId) return false
  return summary.hospitalId !== sessionHospitalId
}

export default function Landing() {
  const navigate = useNavigate()
  const session = loadSession()
  const role = session?.user.role ?? 'hospital_staff'
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [summary, setSummary] = useState<ResourceSummary | null>(null)

  useEffect(() => {
    if (!session) return
    let cancelled = false
    setLoadState('loading')
    fetch(`${API_URL}/dashboard/summary/`, {
      credentials: 'include',
      headers: getAuthHeaders(session),
    })
      .then(async (res) => {
        if (res.status === 401 || res.status === 403) {
          clearSession()
          navigate('/login', { replace: true })
          return null
        }
        if (!res.ok) throw new Error('summary failed')
        return res.json() as Promise<ResourceSummary>
      })
      .then((data) => {
        if (cancelled || !data) return
        if (landingIncludesForeignHospital(data, session.user.hospitalId)) {
          setLoadState('error')
          return
        }
        setSummary(data)
        setLoadState('ready')
      })
      .catch(() => {
        if (!cancelled) setLoadState('error')
      })
    return () => {
      cancelled = true
    }
  }, [navigate, session])

  function handleLogout() {
    clearSession()
    navigate('/login', { replace: true })
  }

  const hospitalLabel = summary?.hospitalName ?? session?.user.hospitalName ?? 'Hospital'

  return (
    <main
      className="landing-page"
      data-testid="landing-page"
      style={{ maxWidth: 960, margin: '0 auto', padding: '32px 16px' }}
    >
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>
          <span
            data-testid="landing-hospital-name"
            dangerouslySetInnerHTML={{ __html: escapeHtml(hospitalLabel) }}
          />
        </h1>
        <button type="button" data-testid="landing-logout" onClick={handleLogout}>
          Logout
        </button>
      </header>

      {role === 'admin' ? (
        <nav data-testid="landing-admin-nav" aria-label="Administrator">
          <Link to="/admin/hospitals/register">Register Hospital</Link>
          <Link to="/admin/users">Manage Users</Link>
        </nav>
      ) : null}

      {role === 'hospital_staff' ? (
        <section data-testid="landing-staff-widgets" aria-label="Hospital resources">
          {loadState === 'loading' ? <p role="status">Loading resource availability…</p> : null}
          {loadState === 'error' ? (
            <p role="alert" data-testid="landing-load-error">
              Unable to load blood availability and bed counts. Try again shortly.
            </p>
          ) : null}
          {loadState === 'ready' && summary ? (
            <div data-testid="landing-resource-counts">
              <p>
                ICU beds available:{' '}
                <strong data-testid="landing-icu-count">{formatResourceCount(summary.icuBedsAvailable)}</strong>
              </p>
              <p>
                Blood units available:{' '}
                <strong data-testid="landing-blood-count">{formatResourceCount(summary.bloodUnitsAvailable)}</strong>
              </p>
            </div>
          ) : null}
          <nav data-testid="landing-staff-nav" aria-label="Staff navigation" style={{ marginTop: 24 }}>
            <Link to="/emergency/new">Emergency request</Link>
            <Link to="/blood">Blood</Link>
            <Link to="/beds">Beds</Link>
            <Link to="/equipment">Equipment</Link>
            <Link to="/operating-rooms">Operating rooms</Link>
            <Link to="/notifications">Notifications</Link>
          </nav>
        </section>
      ) : null}

      {role !== 'admin' && role !== 'hospital_staff' ? (
        <p data-testid="landing-coordinator-hint">Use the emergency workflow from the menu.</p>
      ) : null}

    </main>
  )
}

export function roleMayAccessCityCommandCenter(userRole: UserRole): boolean {
  return userRole === 'admin'
}
