import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AppRoutes } from '../App'
import { mockStaffApi } from '../test/mockApi'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

describe('Patient privacy page (B23)', () => {
  it('states the HIPAA compliance and lists every safeguard with how it is done', async () => {
    mockStaffApi({ role: null })
    renderAt('/privacy')
    expect(await screen.findByRole('heading', { level: 1, name: 'CityCare is HIPAA compliant.' })).toBeInTheDocument()
    const rows = within(screen.getByRole('table')).getAllByRole('rowheader').map((th) => th.textContent)
    expect(rows).toEqual(
      expect.arrayContaining([
        expect.stringContaining('Minimum necessary'),
        expect.stringContaining('Access control'),
        expect.stringContaining('Automatic log-off'),
        expect.stringContaining('Audit controls'),
        expect.stringContaining('Transmission security'),
      ]),
    )
    expect(screen.getByText(/never enter real patient information/)).toBeInTheDocument()
  })

  it('is linked from the public footer', async () => {
    mockStaffApi({ role: null })
    renderAt('/')
    const footer = await screen.findByRole('contentinfo')
    expect(within(footer).getByRole('link', { name: 'Patient privacy' })).toHaveAttribute('href', '/privacy')
  })
})
