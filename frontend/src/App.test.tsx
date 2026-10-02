import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('App', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders the home page and reports API status', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), { status: 200 }),
    )
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Hospital Care' })).toBeInTheDocument()
    expect(await screen.findByText('up')).toBeInTheDocument()
  })
})
