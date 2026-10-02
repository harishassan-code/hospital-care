import { useEffect, useState } from 'react'
import { apiGet } from '../api/client'

type Health = { status: string }

export default function Home() {
  const [api, setApi] = useState<'checking' | 'up' | 'down'>('checking')

  useEffect(() => {
    apiGet<Health>('/health/')
      .then((h) => setApi(h.status === 'ok' ? 'up' : 'down'))
      .catch(() => setApi('down'))
  }, [])

  return (
    <main style={{ maxWidth: 720, margin: '0 auto', padding: '48px 16px' }}>
      <h1>Hospital Care</h1>
      <p style={{ color: 'var(--muted)' }}>
        City-wide hospital emergency resource coordination platform.
      </p>
      <p>
        API status:{' '}
        <strong data-testid="api-status" style={{ color: api === 'up' ? 'var(--ok)' : 'var(--accent)' }}>
          {api}
        </strong>
      </p>
    </main>
  )
}
