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

  it.each(PLANNED.map((p) => [p.path, p.label, p.sprint] as const))('%s says when %s arrives', async (path, label, sprint) => {
    mockStaffApi({ role: 'doctor' })
    renderAt(path)
    expect(await screen.findByRole('heading', { level: 1, name: label })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: `${label}: coming in Sprint ${sprint}` })).toBeInTheDocument()
  })
})
