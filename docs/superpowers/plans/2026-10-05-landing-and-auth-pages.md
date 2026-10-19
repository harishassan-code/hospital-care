# Landing, Log in and Sign up: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the public landing page, log-in page and patient sign-up page for one branded hospital, in the "Follow the line" wayfinding design.

**Architecture:** React Router routes `/`, `/login`, `/signup`, `*`. Pure logic (validation, schedule maths, API error mapping) lives in small TS modules with unit tests; components are thin and styled with CSS Modules that read only from `src/styles/tokens.css`. Live hospital status comes from `getPublicStatus()`, which returns sample data until the backend endpoint exists.

**Tech Stack:** React 19, TypeScript, Vite 8, React Router 7, CSS Modules, Vitest 5 + Testing Library + user-event, `@fontsource-variable` fonts.

**Spec:** `docs/superpowers/specs/2026-10-05-landing-and-auth-pages-design.md`

## Global Constraints

- **Do not commit or push.** The user approves every commit. Each task ends with a checkpoint (tests green), not a commit.
- Work in `frontend/`. All commands below run from `frontend/`.
- Colours only from tokens: `--wall #EDF2EE`, `--sign #0F2A26`, `--sign-text #F3F7F4`, `--ink #14211E`, `--ink-muted #4D5E59`, `--surface #FFFFFF`, `--rule #CBD6D0`, `--line-emergency #C8202F`, `--line-clinics #1C5BB8`, `--line-portal #00806A`.
- No gradients, glows, or box-shadow "lift" effects.
- Fonts: Overpass (display), Atkinson Hyperlegible Next (body), Atkinson Hyperlegible Mono (data). Self-hosted.
- Copy is sentence case, plain verbs; error text exactly as in the spec's message table.
- Quality floor: 3px focus ring, skip link, labelled inputs, `aria-invalid` + `aria-describedby`, ≥ 44px targets, no horizontal scroll at 375px, `prefers-reduced-motion` respected.
- `npm run lint`, `npm test`, `npm run build` must all pass at the end of every task.

## File map

| File | Responsibility |
|---|---|
| `src/config/hospital.ts` | Per-hospital branding and contact details |
| `src/styles/tokens.css` | Design tokens (CSS custom properties) |
| `src/styles/global.css` | Reset, base type, focus ring, skip link, reduced motion |
| `src/api/client.ts` | `apiGet`, `apiPost`, `ApiError` |
| `src/api/auth.ts` | `login`, `signup`, `AuthError`, `authErrorMessage` |
| `src/api/publicStatus.ts` | Types + `getPublicStatus()` sample data, `ER_STATUS_LABEL` |
| `src/features/auth/validation.ts` | Login/sign-up field rules |
| `src/features/landing/schedule.ts` | Shift maths: minutes, segments, in-now, sort, filter |
| `src/components/form/*` | `TextField`, `PasswordField`, `Checkbox`, `Button`/`ButtonLink`, `FormAlert` |
| `src/components/layout/*` | `SiteHeader`, `SiteFooter`, `AuthLayout` |
| `src/features/landing/*` | `WayfindingSign`, `FloorLines`, `Destination`, `EmergencyStatus`, `DoctorSchedule`, `SignInOptions` |
| `src/pages/*` | `LandingPage`, `LoginPage`, `SignupPage`, `NotFoundPage` |

---

### Task 1: Foundations: fonts, tokens, config, routes

**Files:**
- Create: `src/config/hospital.ts`, `src/styles/tokens.css`, `src/styles/global.css`, `src/pages/NotFoundPage.tsx`, `src/pages/NotFoundPage.module.css`, placeholder `src/pages/LandingPage.tsx`, `LoginPage.tsx`, `SignupPage.tsx`
- Modify: `src/main.tsx`, `src/App.tsx`, `src/App.test.tsx`
- Delete: `src/index.css`, `src/pages/Home.tsx`

**Interfaces:**
- Produces: `hospital` object `{ name, shortName, monogram, emergencyNumber, mainPhone, address, visitingHours, brandColor }` (all strings); `App` with routes.

- [ ] **Step 1: Install dependencies**

Run: `npm install @fontsource-variable/overpass @fontsource-variable/atkinson-hyperlegible-next @fontsource-variable/atkinson-hyperlegible-mono && npm install -D @testing-library/user-event`

- [ ] **Step 2: Write the failing route test** (`src/App.test.tsx`)

```tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AppRoutes } from './App'

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
```

- [ ] **Step 3: Run it, expect FAIL** (`AppRoutes` not exported). Run: `npx vitest run src/App.test.tsx`

- [ ] **Step 4: Implement**
  - `App.tsx` exports `AppRoutes` (the `<Routes>` block) and default `App` (`<BrowserRouter><AppRoutes/></BrowserRouter>`).
  - `NotFoundPage`: `h1` "This page doesn’t exist", paragraph, `Link to="/"` "Back to {hospital.name}".
  - `main.tsx` imports the three fontsource packages, `tokens.css`, `global.css`; sets `--sign` from `hospital.brandColor` on `document.documentElement`.
  - `hospital.ts`:

```ts
export const hospital = {
  name: 'Northgate General Hospital',
  shortName: 'Northgate General',
  monogram: 'NG',
  emergencyNumber: '1122',
  mainPhone: '(021) 3400 0000',
  address: 'Plot 14, Shahrah-e-Faisal, Karachi',
  visitingHours: '11:00–13:00 and 17:00–20:00 daily',
  brandColor: '#0F2A26',
} as const
```

- [ ] **Step 5: Run tests, lint, build → all pass.** Checkpoint (no commit).

---

### Task 2: Form validation rules

**Files:** Create `src/features/auth/validation.ts`, Test `src/features/auth/validation.test.ts`

**Interfaces:**
- Produces:
  - `type FieldErrors<K extends string> = Partial<Record<K, string>>`
  - `type LoginValues = { email: string; password: string }`
  - `type SignupValues = { fullName: string; email: string; phone: string; password: string; confirmPassword: string; acceptTerms: boolean }`
  - `validateLogin(v: LoginValues): FieldErrors<keyof LoginValues>`
  - `validateSignup(v: SignupValues): FieldErrors<keyof SignupValues>`
  - `firstErrorKey<K extends string>(errors: FieldErrors<K>, order: readonly K[]): K | undefined`

- [ ] **Step 1: Failing tests**

```ts
import { describe, expect, it } from 'vitest'
import { firstErrorKey, validateLogin, validateSignup, type SignupValues } from './validation'

const validSignup: SignupValues = {
  fullName: 'Sara Ahmed', email: 'sara@example.com', phone: '',
  password: 'blood-bank-7', confirmPassword: 'blood-bank-7', acceptTerms: true,
}

describe('validateLogin', () => {
  it('requires email and password', () => {
    expect(validateLogin({ email: '', password: '' })).toEqual({
      email: 'Enter your email address', password: 'Enter your password',
    })
  })
  it('rejects malformed email', () => {
    expect(validateLogin({ email: 'sara@', password: 'x' }).email).toBe('Enter an email like name@example.com')
  })
  it('accepts valid input', () => {
    expect(validateLogin({ email: ' sara@example.com ', password: 'x' })).toEqual({})
  })
})

describe('validateSignup', () => {
  it('accepts a valid form', () => expect(validateSignup(validSignup)).toEqual({}))
  it('requires a name', () =>
    expect(validateSignup({ ...validSignup, fullName: '  ' }).fullName).toBe('Enter your full name'))
  it('requires a password', () =>
    expect(validateSignup({ ...validSignup, password: '', confirmPassword: '' }).password).toBe('Create a password'))
  it('enforces 8 characters', () =>
    expect(validateSignup({ ...validSignup, password: 'abc1', confirmPassword: 'abc1' }).password).toBe('Use at least 8 characters'))
  it('rejects digits-only passwords', () =>
    expect(validateSignup({ ...validSignup, password: '12345678', confirmPassword: '12345678' }).password).toBe('Use letters as well as numbers'))
  it('checks confirmation', () =>
    expect(validateSignup({ ...validSignup, confirmPassword: 'other-pass-1' }).confirmPassword).toBe('Passwords don’t match'))
  it('phone is optional but must look like a phone number', () => {
    expect(validateSignup({ ...validSignup, phone: '+92 300-1234567' }).phone).toBeUndefined()
    expect(validateSignup({ ...validSignup, phone: 'call me' }).phone).toBe('Enter a phone number using digits, spaces, + or -')
  })
  it('requires terms', () =>
    expect(validateSignup({ ...validSignup, acceptTerms: false }).acceptTerms).toBe('Agree to the terms to create an account'))
})

describe('firstErrorKey', () => {
  it('returns the first key in form order', () =>
    expect(firstErrorKey({ password: 'x', email: 'y' }, ['email', 'password'] as const)).toBe('email'))
})
```

- [ ] **Step 2: Run, expect FAIL.** `npx vitest run src/features/auth`
- [ ] **Step 3: Implement** with `EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/`, `PHONE = /^\+?[\d\s-]{7,20}$/`; trim email/name before checking; confirm checked only when password valid-or-present.
- [ ] **Step 4: Run, expect PASS.** Checkpoint.

---

### Task 3: API client and auth calls

**Files:** Modify `src/api/client.ts`; Create `src/api/auth.ts`; Test `src/api/auth.test.ts`

**Interfaces:**
- Consumes: none.
- Produces:
  - `class ApiError extends Error { status: number; body: unknown }` (status `0` = network failure)
  - `apiPost<T>(path: string, body: unknown): Promise<T>`: JSON, `credentials: 'include'`, `X-CSRFToken` from `csrftoken` cookie
  - `type AuthErrorKind = 'invalid_credentials' | 'email_taken' | 'rejected' | 'unavailable'`
  - `class AuthError extends Error { kind: AuthErrorKind }`
  - `login(v: { email: string; password: string }): Promise<void>` → `POST /auth/login/`
  - `signup(v: { fullName: string; email: string; phone: string; password: string }): Promise<void>` → `POST /auth/signup/`
  - `authErrorMessage(kind: AuthErrorKind): string`

- [ ] **Step 1: Failing tests**

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthError, authErrorMessage, login, signup } from './auth'

const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => vi.restoreAllMocks())

async function kindOf(p: Promise<unknown>) {
  try { await p } catch (e) { return (e as AuthError).kind }
  return 'resolved'
}

describe('login', () => {
  it('posts credentials as JSON with cookies', async () => {
    const f = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(200))
    await login({ email: 'a@b.co', password: 'pw' })
    const [url, init] = f.mock.calls[0]
    expect(String(url)).toMatch(/\/auth\/login\/$/)
    expect(init?.method).toBe('POST')
    expect(init?.credentials).toBe('include')
    expect(JSON.parse(String(init?.body))).toEqual({ email: 'a@b.co', password: 'pw' })
  })
  it.each([400, 401])('maps %i to invalid_credentials', async (status) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(status))
    expect(await kindOf(login({ email: 'a@b.co', password: 'pw' }))).toBe('invalid_credentials')
  })
  it.each([403, 404, 500])('maps %i to unavailable', async (status) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(status))
    expect(await kindOf(login({ email: 'a@b.co', password: 'pw' }))).toBe('unavailable')
  })
  it('maps network failure to unavailable', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    expect(await kindOf(login({ email: 'a@b.co', password: 'pw' }))).toBe('unavailable')
  })
})

describe('signup', () => {
  const v = { fullName: 'Sara', email: 'a@b.co', phone: '', password: 'blood-bank-7' }
  it('maps 409 to email_taken', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(409))
    expect(await kindOf(signup(v))).toBe('email_taken')
  })
  it('maps 400 with an email error to email_taken', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(400, { email: ['exists'] }))
    expect(await kindOf(signup(v))).toBe('email_taken')
  })
  it('maps other 400s to rejected', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(400, { password: ['too common'] }))
    expect(await kindOf(signup(v))).toBe('rejected')
  })
  it('resolves on 201', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json(201))
    expect(await kindOf(signup(v))).toBe('resolved')
  })
})

it('has a message for every kind', () => {
  expect(authErrorMessage('invalid_credentials')).toBe('That email and password don’t match an account')
  expect(authErrorMessage('email_taken')).toBe('An account with this email already exists. Log in instead.')
  expect(authErrorMessage('rejected')).toBe('The hospital couldn’t accept these details. Check them and try again.')
  expect(authErrorMessage('unavailable')).toBe('The hospital’s server didn’t respond. Try again in a moment.')
})
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** `apiPost` (catch fetch rejection → `ApiError(0)`; non-OK → parse JSON body if possible → `ApiError(status, body)`), then `auth.ts` mapping per the interface list. Signup body uses snake_case: `{ full_name, email, phone, password }`.
- [ ] **Step 4: Run, expect PASS.** Checkpoint.

---

### Task 4: Form components

**Files:** Create in `src/components/form/`: `TextField.tsx`, `PasswordField.tsx`, `Checkbox.tsx`, `Button.tsx`, `FormAlert.tsx`, `Form.module.css`, test `PasswordField.test.tsx`

**Interfaces:**
- `TextField({ id, label, value, onChange: (v: string) => void, error?, hint?, type?: 'text'|'email'|'tel', autoComplete?, optional?: boolean, ref })`: label shows "(optional)" when `optional`; input gets `aria-invalid` and `aria-describedby` = hint id + error id.
- `PasswordField({ id, label, value, onChange, error?, hint?, autoComplete, ref })`: adds a `Show`/`Hide` button (`aria-pressed`, `aria-controls`).
- `Checkbox({ id, children, checked, onChange: (v: boolean) => void, error?, ref })`
- `Button({ children, type?, pending?, pendingLabel? })`: full-width primary; when `pending`, disabled and shows `pendingLabel`.
- `ButtonLink({ to, children, variant?: 'primary' | 'secondary' })`: React Router `Link` styled as a button.
- `FormAlert({ children })`: `role="alert"`, red left rule.
- React 19: `ref` is a normal prop (`ref?: React.Ref<HTMLInputElement>`).

- [ ] **Step 1: Failing test**

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expect, it } from 'vitest'
import { PasswordField } from './PasswordField'

function Harness() {
  const [v, setV] = useState('')
  return <PasswordField id="pw" label="Password" value={v} onChange={setV} autoComplete="current-password" error="Enter your password" />
}

it('toggles visibility and links the error to the input', async () => {
  render(<Harness />)
  const input = screen.getByLabelText('Password')
  expect(input).toHaveAttribute('type', 'password')
  expect(input).toHaveAttribute('aria-invalid', 'true')
  expect(input).toHaveAccessibleDescription('Enter your password')
  await userEvent.click(screen.getByRole('button', { name: 'Show password' }))
  expect(input).toHaveAttribute('type', 'text')
  expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true')
})
```

- [ ] **Step 2: FAIL → Step 3: implement → Step 4: PASS.** Styles: label 600 weight; input 48px min-height, 2px `--rule` border, radius 4px, `:focus-visible` uses global ring; error text `--line-emergency` with a "!" glyph prefix; primary button `--line-portal` background, white text, Overpass 700 uppercase, 52px tall. Checkpoint.

---

### Task 5: Auth layout + Log in page

**Files:** Create `src/components/layout/AuthLayout.tsx` + `.module.css`, `src/pages/LoginPage.tsx` + `.module.css`, test `src/pages/LoginPage.test.tsx`

**Interfaces:**
- Consumes: `validateLogin`, `firstErrorKey`, `login`, `AuthError`, `authErrorMessage`, form components, `hospital`.
- Produces: `AuthLayout({ title, children })`. Title is the sign-row text (e.g. "Sign in"), rendered uppercase via CSS, as the page `h1`.

- [ ] **Step 1: Failing tests**

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import LoginPage from './LoginPage'

const renderPage = () => render(<MemoryRouter><LoginPage /></MemoryRouter>)
afterEach(() => vi.restoreAllMocks())

describe('LoginPage', () => {
  it('shows field errors and focuses the first invalid field', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(screen.getByText('Enter your email address')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveFocus()
  })

  it('tells the user when the credentials are wrong', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }))
    renderPage()
    await userEvent.type(screen.getByLabelText('Email'), 'sara@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('That email and password don’t match an account')
  })

  it('explains when the server is unreachable', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    renderPage()
    await userEvent.type(screen.getByLabelText('Email'), 'sara@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'anything-1')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The hospital’s server didn’t respond')
  })

  it('reveals password help', async () => {
    renderPage()
    const toggle = screen.getByRole('button', { name: 'Forgot your password?' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(screen.getByText(/Ask the front desk to reset it/)).toBeVisible()
  })

  it('links new patients to sign up', () => {
    renderPage()
    expect(screen.getByRole('link', { name: 'Create an account' })).toHaveAttribute('href', '/signup')
  })
})
```

- [ ] **Step 2: FAIL → Step 3: implement → Step 4: PASS.**
  - `AuthLayout`: `<header>` sign band (`--sign` bg) containing `Link to="/"` "← {hospital.name}" and the sign row (`--line-portal` 12px chip + `h1`); `<main id="main">` centred card max-width 440px, white, `border-left: 6px solid var(--line-portal)`.
  - `LoginPage`: controlled state; on submit validate → set errors → focus first error via refs map; else `pending` → `login()` → on success `navigate('/')`; on `AuthError` set alert text.
  - Checkpoint.

---

### Task 6: Sign up page

**Files:** Create `src/pages/SignupPage.tsx` (+ reuse `LoginPage.module.css` patterns in `SignupPage.module.css`), test `src/pages/SignupPage.test.tsx`

- [ ] **Step 1: Failing tests**

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SignupPage from './SignupPage'

const renderPage = () => render(<MemoryRouter><SignupPage /></MemoryRouter>)
afterEach(() => vi.restoreAllMocks())

async function fillValid(confirm = 'blood-bank-7') {
  await userEvent.type(screen.getByLabelText('Full name'), 'Sara Ahmed')
  await userEvent.type(screen.getByLabelText('Email'), 'sara@example.com')
  await userEvent.type(screen.getByLabelText('Password'), 'blood-bank-7')
  await userEvent.type(screen.getByLabelText('Confirm password'), confirm)
  await userEvent.click(screen.getByRole('checkbox'))
}

describe('SignupPage', () => {
  it('tells staff they do not sign up here', () => {
    renderPage()
    expect(screen.getByText(/Your administrator creates staff accounts/)).toBeInTheDocument()
  })

  it('validates mismatched passwords and unchecked terms', async () => {
    renderPage()
    await userEvent.type(screen.getByLabelText('Password'), 'blood-bank-7')
    await userEvent.type(screen.getByLabelText('Confirm password'), 'blood-bank-8')
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByText('Passwords don’t match')).toBeInTheDocument()
    expect(screen.getByText('Agree to the terms to create an account')).toBeInTheDocument()
    expect(screen.getByLabelText('Full name')).toHaveFocus()
  })

  it('reports an email that is already registered', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 409 }))
    renderPage()
    await fillValid()
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('An account with this email already exists')
  })

  it('confirms success and points to log in', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 201 }))
    renderPage()
    await fillValid()
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Account created. You can now log in.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
  })
})
```

- [ ] **Step 2: FAIL → Step 3: implement → Step 4: PASS.** Field order for focus: `fullName, email, phone, password, confirmPassword, acceptTerms`. Password hint: "At least 8 characters, not only numbers". Checkpoint.

---

### Task 7: Public status data + schedule maths

**Files:** Create `src/api/publicStatus.ts`, `src/features/landing/schedule.ts`, test `src/features/landing/schedule.test.ts`

**Interfaces:**
- `type ErStatus = 'accepting' | 'busy' | 'diverting'`
- `interface Doctor { id: string; name: string; department: string; start: string; end: string }`
- `interface PublicStatus { updatedAt: string; emergency: { status: ErStatus; waitMinutes: number; waitingCount: number }; doctors: Doctor[] }`
- `ER_STATUS_LABEL: Record<ErStatus, string>` = Accepting patients / Very busy / Not accepting ambulances
- `getPublicStatus(): Promise<PublicStatus>`: 14 sample doctors across Emergency medicine, General medicine, Cardiology, Paediatrics, Orthopaedics, Gynaecology, including overnight shifts; `updatedAt` = now.
- `toMinutes(hhmm: string): number`
- `shiftSegments(start: string, end: string): Array<[number, number]>` (minutes; wraps midnight into two segments)
- `isInNow(d: Pick<Doctor,'start'|'end'>, now: Date): boolean`
- `minutesOfDay(now: Date): number`
- `departmentsOf(doctors: Doctor[]): string[]` (sorted, unique)
- `sortForDisplay(doctors: Doctor[], now: Date): Doctor[]` (in now first, then by start)

- [ ] **Step 1: Failing tests**

```ts
import { describe, expect, it } from 'vitest'
import { departmentsOf, isInNow, shiftSegments, sortForDisplay, toMinutes } from './schedule'
import type { Doctor } from '../../api/publicStatus'

const at = (hhmm: string) => { const d = new Date(2026, 9, 5); d.setHours(+hhmm.slice(0, 2), +hhmm.slice(3)); return d }
const doc = (id: string, department: string, start: string, end: string): Doctor => ({ id, name: `Dr ${id}`, department, start, end })

describe('schedule', () => {
  it('converts HH:MM to minutes', () => expect(toMinutes('09:30')).toBe(570))
  it('keeps day shifts as one segment', () => expect(shiftSegments('09:00', '13:00')).toEqual([[540, 780]]))
  it('splits overnight shifts at midnight', () => expect(shiftSegments('20:00', '08:00')).toEqual([[1200, 1440], [0, 480]]))
  it('knows who is in now, including overnight', () => {
    const day = doc('a', 'Cardiology', '09:00', '13:00')
    const night = doc('b', 'Emergency medicine', '20:00', '08:00')
    expect(isInNow(day, at('10:00'))).toBe(true)
    expect(isInNow(day, at('13:00'))).toBe(false)
    expect(isInNow(night, at('23:00'))).toBe(true)
    expect(isInNow(night, at('07:59'))).toBe(true)
    expect(isInNow(night, at('12:00'))).toBe(false)
  })
  it('lists departments once, sorted', () =>
    expect(departmentsOf([doc('a', 'Paediatrics', '09:00', '10:00'), doc('b', 'Cardiology', '09:00', '10:00'), doc('c', 'Paediatrics', '11:00', '12:00')]))
      .toEqual(['Cardiology', 'Paediatrics']))
  it('puts doctors who are in first, then by start time', () => {
    const list = [doc('late', 'X', '16:00', '20:00'), doc('early', 'X', '06:00', '09:00'), doc('now', 'X', '09:00', '13:00')]
    expect(sortForDisplay(list, at('10:00')).map((d) => d.id)).toEqual(['now', 'early', 'late'])
  })
})
```

- [ ] **Step 2: FAIL → Step 3: implement → Step 4: PASS.** Checkpoint.

---

### Task 8: Landing page

**Files:** Create in `src/features/landing/`: `FloorLines.tsx`, `Destination.tsx`, `WayfindingSign.tsx`, `EmergencyStatus.tsx`, `DoctorSchedule.tsx`, `SignInOptions.tsx`, `Landing.module.css`, `DoctorSchedule.test.tsx`; `src/components/layout/SiteHeader.tsx`, `SiteFooter.tsx`, `Site.module.css`; `src/pages/LandingPage.tsx`, test `src/pages/LandingPage.test.tsx`

**Pre-step:** load the `dataviz` skill before writing `DoctorSchedule` (it is a timeline chart).

**Interfaces:**
- `LINES = [{ id: 'emergency', color: 'var(--line-emergency)' }, { id: 'doctors', color: 'var(--line-clinics)' }, { id: 'sign-in', color: 'var(--line-portal)' }] as const` exported from `FloorLines.tsx`. Line `i` sits at gutter x = `72 - i*24` px (first destination's line is innermost, so turns never cross).
- `FloorLines({ through: number[], turn?: number })`: gutter cell (`aria-hidden`). Draws a full-height vertical for each index in `through`; for `turn`, a vertical from top to `--turn-y` then a horizontal to the gutter's right edge.
- `Destination({ index, title, eyebrow?, children })`: `<section id={LINES[index].id} aria-labelledby>`; grid `[gutter 96px][content]`; renders `FloorLines through={indices > index} turn={index}`; `h2` title.
- `WayfindingSign({ status: PublicStatus | null, error: boolean, now: Date })`: `<nav aria-label="On this page">` with 3 `<a href="#…">` rows: chip, LABEL, detail, down-arrow SVG.
- `EmergencyStatus({ emergency, updatedAt })`, `DoctorSchedule({ doctors: Doctor[], now: Date })`, `SignInOptions()`.
- `LandingPage`: fetches `getPublicStatus()` on mount; `now` state refreshed every 60 s.

- [ ] **Step 1: Failing tests**

`src/features/landing/DoctorSchedule.test.tsx`:

```tsx
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { DoctorSchedule } from './DoctorSchedule'
import type { Doctor } from '../../api/publicStatus'

const now = new Date(2026, 9, 5, 10, 0)
const doctors: Doctor[] = [
  { id: '1', name: 'Dr. Ayesha Khan', department: 'Cardiology', start: '09:00', end: '13:00' },
  { id: '2', name: 'Dr. Sana Malik', department: 'Paediatrics', start: '14:00', end: '18:00' },
  { id: '3', name: 'Dr. Usman Farooq', department: 'Emergency medicine', start: '20:00', end: '08:00' },
]

it('tags doctors who are in now and shows their hours', () => {
  render(<DoctorSchedule doctors={doctors} now={now} />)
  const ayesha = screen.getByRole('listitem', { name: /Ayesha Khan/ })
  expect(within(ayesha).getByText('In now')).toBeInTheDocument()
  expect(within(ayesha).getByText('09:00–13:00')).toBeInTheDocument()
  expect(within(screen.getByRole('listitem', { name: /Sana Malik/ })).queryByText('In now')).toBeNull()
})

it('filters by department', async () => {
  render(<DoctorSchedule doctors={doctors} now={now} />)
  await userEvent.click(screen.getByRole('button', { name: 'Paediatrics' }))
  expect(screen.getByRole('button', { name: 'Paediatrics' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getAllByRole('listitem')).toHaveLength(1)
  await userEvent.click(screen.getByRole('button', { name: 'All' }))
  expect(screen.getAllByRole('listitem')).toHaveLength(3)
})

it('says so when nothing is published', () => {
  render(<DoctorSchedule doctors={[]} now={now} />)
  expect(screen.getByText('No doctor schedules are published for today.')).toBeInTheDocument()
})
```

`src/pages/LandingPage.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, it } from 'vitest'
import LandingPage from './LandingPage'
import { hospital } from '../config/hospital'

it('shows the hospital, the sign and live emergency status', async () => {
  render(<MemoryRouter><LandingPage /></MemoryRouter>)
  expect(screen.getAllByText(hospital.name).length).toBeGreaterThan(0)
  expect(screen.getByRole('heading', { level: 1, name: 'Where do you need to go?' })).toBeInTheDocument()
  const sign = screen.getByRole('navigation', { name: 'On this page' })
  const hrefs = Array.from(sign.querySelectorAll('a')).map((a) => a.getAttribute('href'))
  expect(hrefs).toEqual(['#emergency', '#doctors', '#sign-in'])
  expect(await screen.findAllByText(/min wait/)).not.toHaveLength(0)
  expect(screen.getByRole('link', { name: `Emergency: ${hospital.emergencyNumber}` })).toHaveAttribute('href', `tel:${hospital.emergencyNumber}`)
})
```

- [ ] **Step 2: FAIL → Step 3: implement → Step 4: PASS.**
  - Desktop (≥ 960px): page grid `96px 1fr`, content max 1120px. Sign spans both columns; lines emerge from its bottom edge.
  - Below 960px: gutters `display: none`; `Destination` gets `border-left: 6px solid` its line colour.
  - Line draw animation: `@keyframes draw { from { transform: scaleY(0) } }`, 600ms ease-out, `transform-origin: top`; disabled under reduced motion.
  - Schedule: row grid `[who 15rem][timeline 1fr]`; timeline hidden below 720px. Bars `--line-clinics`; not-in-now bars at 35% tint via `color-mix`; now marker 2px `--ink` with mono "Now HH:MM" label. Axis ticks every 3 h, mono, `--ink-muted`.
  - Checkpoint.

---

### Task 9: Visual verification and polish

- [ ] Run `npm run dev`; open in the browser pane at 1280×800 and 375×812.
- [ ] Screenshot landing (top, emergency, doctors, sign-in), login (empty + errors), signup.
- [ ] Check: no horizontal scroll at 375, focus ring visible on keyboard tab, lines don't cross, contrast.
- [ ] Fix issues; re-run `npm run lint && npm test && npm run build`.
- [ ] Report to user with screenshots. **No commit.**
