import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AppRoutes } from './App'
import { PLANNED } from './features/staff/planned'
import { mockStaffApi } from './test/mockApi'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

describe('routes', () => {
  it('shows a not-found page with a link home for unknown paths', () => {
    renderAt('/nope')
    expect(screen.getByRole('heading', { name: 'This page doesn’t exist' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to/i })).toHaveAttribute('href', '/')
  })
})

describe('route placeholders (issue #5)', () => {
  afterEach(() => vi.restoreAllMocks())

  it('has none left: every MVP module has its page (Sprint 8)', () => {
    expect(PLANNED).toEqual([])
  })

  it.each([
    ['/staff/donors', 'Donors'],
    ['/staff/ambulances', 'Ambulances'],
    ['/staff/alerts', 'Alerts'],
    ['/staff/command-centre', 'City command centre'],
    ['/staff/audit', 'Audit log'],
  ])('%s opens the %s page for an admin', async (path, label) => {
    mockStaffApi({ role: 'admin' })
    renderAt(path)
    expect(await screen.findByRole('heading', { level: 1, name: label })).toBeInTheDocument()
    expect(screen.queryByText(/coming in Sprint/)).not.toBeInTheDocument()
  })
})
