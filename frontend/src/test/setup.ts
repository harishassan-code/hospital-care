import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// Vitest globals are off, so Testing Library can't register its own cleanup.
afterEach(() => cleanup())

// The default 1 s for findBy* is too tight when every worker builds jsdom at once (full run, slow CI).
configure({ asyncUtilTimeout: 4000 })
