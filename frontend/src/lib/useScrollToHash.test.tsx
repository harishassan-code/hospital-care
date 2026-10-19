import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { useScrollToHash } from './useScrollToHash'

function Page({ ready }: { ready: boolean }) {
  useScrollToHash(ready)
  return <section id="attention">Needs attention</section>
}

afterEach(() => vi.restoreAllMocks())

it('scrolls to the element named by the URL hash once the page is ready', () => {
  const scroll = vi.fn()
  Element.prototype.scrollIntoView = scroll
  const { rerender } = render(
    <MemoryRouter initialEntries={['/staff#attention']}>
      <Page ready={false} />
    </MemoryRouter>,
  )
  expect(scroll).not.toHaveBeenCalled()
  rerender(
    <MemoryRouter initialEntries={['/staff#attention']}>
      <Page ready />
    </MemoryRouter>,
  )
  expect(scroll).toHaveBeenCalledTimes(1)
  expect(scroll.mock.contexts[0]).toHaveProperty('id', 'attention')
})
