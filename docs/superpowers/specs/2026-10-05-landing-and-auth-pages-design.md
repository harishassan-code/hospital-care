# Landing, Log in and Sign up: Design

**Status:** Approved by Haris (Scrum Master / frontend lead), 5 Oct 2026
**Scope:** public frontend only. No backend endpoints are built here.

## Product context

Hospital Care is a template that each hospital installs and brands for itself (one hospital per install).
There are two kinds of account:

- **Hospital accounts** (admin, staff, nurses, doctors) use the site as a management tool. They are created
  by the hospital's administrator; staff never sign up themselves.
- **Patient / public accounts** see public information: ER availability and wait time, and when each doctor
  is in. Patients can sign up themselves.

The landing page is a specific hospital's public front door. "Hospital Care" appears only as
"Powered by Hospital Care" in the footer.

## Visual direction: "Follow the line"

Based on hospital wayfinding: overhead direction signs and coloured floor lines. The hero is an overhead
sign whose rows link to "destinations" on the page; each destination's coloured floor line runs down a
left gutter and turns into its section, while the remaining lines carry on.

### Tokens

| Token | Hex | Use |
|---|---|---|
| `--wall` | `#EDF2EE` | Page background (pale surgical green) |
| `--sign` | `#0F2A26` | Overhead sign, auth header band. **Per-hospital brand colour** |
| `--sign-text` | `#F3F7F4` | Text on sign |
| `--ink` | `#14211E` | Body text |
| `--ink-muted` | `#4D5E59` | Secondary text (AA on wall and white) |
| `--surface` | `#FFFFFF` | Cards, forms |
| `--rule` | `#CBD6D0` | Borders and dividers |
| `--line-emergency` | `#C8202F` | Emergency information only |
| `--line-clinics` | `#1C5BB8` | Doctors / schedules |
| `--line-portal` | `#00806A` | Sign-in / accounts (validated: chroma, CVD and contrast checks pass with red + blue) |

No gradients, glows or drop-shadow "lift" effects.

### Type

- **Overpass** (display, derived from Highway Gothic road signage): sign rows only (uppercase, heavy) and
  page headings (sentence case).
- **Atkinson Hyperlegible Next** (body): designed for low-vision legibility.
- **Atkinson Hyperlegible Mono** (data): wait times, clock times, phone numbers.

Fonts are self-hosted via `@fontsource-variable/*` packages.

### Motion

Floor lines draw downward once on load (≈600 ms). Disabled under `prefers-reduced-motion: reduce`.
Sign-row arrows nudge on hover/focus. Nothing else animates.

## Pages and routes

| Route | Page |
|---|---|
| `/` | Landing |
| `/login` | Log in (patients and staff, one form) |
| `/signup` | Create a patient account |
| `*` | Not found, with a link home |

### Landing (`/`)

1. **Skip link** "Skip to content".
2. **Header:** monogram + hospital name; "Emergency: 1122" (`tel:` link, red); Log in; Create account.
3. **Hero:** `h1` "Where do you need to go?" and the overhead sign with three rows, each an anchor link to
   its section:
   - EMERGENCY: ER status label and "about N min wait"
   - DOCTORS TODAY: "X of Y doctors in now"
   - SIGN IN: "Patients and hospital staff"

   Under the sign: "Updated HH:MM · Times are estimates. If it's life-threatening, call 1122."
4. **Emergency** (`#emergency`, red line): status as text + icon (*Accepting patients* / *Very busy* /
   *Not accepting ambulances*), estimated wait, people waiting, and "How we decide who's seen first"
   (Immediate / Urgent / Standard, one line each).
5. **Doctors today** (`#doctors`, blue line): department filter (toggle buttons, "All" default); hour grid
   00:00–24:00 (hospitals run around the clock; night shifts such as 20:00–08:00 wrap past midnight and draw
   as two segments) with one bar per doctor, a "now" marker and an "In now" tag. Rows sorted: in now first,
   then by start time. Below 720px the grid hides and each row reads as a list:
   name · department · HH:MM–HH:MM · "In now". No schedules at all: "No doctor schedules are published for
   today."
6. **Sign in** (`#sign-in`, teal line): *Patients & visitors* card (Create account / Log in); *Hospital
   staff* card (Log in + "Your account is set up by your hospital administrator").
7. **Footer:** address, main phone, emergency number, visiting hours, "Powered by Hospital Care".

Mobile: gutter lines hidden; each destination keeps a 6px left stripe in its colour.

### Auth layout (shared)

A dark sign band holding "← {hospital name}" (link to `/`) and a sign row (teal chip + title). Below it, a
centred white form card (max 440px) with the teal floor line along its left edge.

### Log in (`/login`)

- Fields: Email, Password (Show/Hide toggle with `aria-pressed`).
- "Forgot your password?" is a disclosure button revealing: "Ask the front desk to reset it. Staff: ask
  your hospital administrator."
- Submit: "Log in" → "Logging in…" (disabled while pending).
- Link: "New patient? Create an account".
- On success navigate to `/` (placeholder until the app shell, #5, defines the signed-in home).

### Sign up (`/signup`)

- Notice: "Work here? Your administrator creates staff accounts. Log in instead." (links to `/login`)
- Fields: Full name, Email, Phone (optional), Password (hint: "At least 8 characters, not only numbers"),
  Confirm password, checkbox "I agree to {hospital}'s terms of use and privacy notice".
- Submit: "Create account" → "Creating account…".
- Success: replaces the form with "Account created. You can now log in." and a "Log in" link.
- Link: "Already have an account? Log in".

### Validation and messages

| Case | Message |
|---|---|
| Name empty | Enter your full name |
| Email empty | Enter your email address |
| Email malformed | Enter an email like name@example.com |
| Password empty | Enter your password (login) / Create a password (signup) |
| Password < 8 chars | Use at least 8 characters |
| Password all digits | Use letters as well as numbers |
| Confirm empty | Re-enter your password |
| Confirm mismatch | Passwords don't match |
| Phone present but invalid | Enter a phone number using digits, spaces, + or - |
| Terms unchecked | Agree to the terms to create an account |
| Login rejected (400/401) | That email and password don't match an account |
| Email taken (409, or 400 with email error) | An account with this email already exists. Log in instead. |
| Signup rejected for another reason (other 400) | The hospital couldn't accept these details. Check them and try again. |
| Network / 403 / 404 / 5xx | The hospital's server didn't respond. Try again in a moment. |

Field errors show under the field (`aria-invalid`, `aria-describedby`). On a failed submit, focus moves
to the first invalid field. Server errors show in a `FormAlert` (`role="alert"`) above the button.

## Data

- `src/config/hospital.ts`: `name`, `shortName`, `monogram`, `emergencyNumber`, `mainPhone`, `address`,
  `visitingHours`, `brandColor`. Placeholder: "Northgate General Hospital".
- `src/api/publicStatus.ts`: `getPublicStatus(): Promise<PublicStatus>` returns sample data for now
  (shape = the future `GET /api/public/status/` response):
  `{ updatedAt, emergency: { status, waitMinutes, waitingCount }, doctors: [{ id, name, department, start, end }] }`
  with `start`/`end` as `"HH:MM"`.
- `src/api/auth.ts`: `login({ email, password })` → `POST /api/auth/login/`;
  `signup({ fullName, email, phone, password })` → `POST /api/auth/signup/`. Both throw `AuthError` with
  `kind: 'invalid_credentials' | 'email_taken' | 'rejected' | 'unavailable'`.
- `src/api/client.ts`: adds `apiPost` that sends JSON with credentials and the `csrftoken` cookie as
  `X-CSRFToken`.

## Code layout

```
src/config/hospital.ts
src/styles/tokens.css, global.css
src/api/client.ts, auth.ts, publicStatus.ts
src/components/form/   TextField, PasswordField, Checkbox, Button, FormAlert (+ .module.css)
src/components/layout/ SiteHeader, SiteFooter, AuthLayout (+ .module.css)
src/features/landing/  WayfindingSign, Destination, EmergencyStatus, DoctorSchedule, SignInOptions, schedule.ts
src/features/auth/     validation.ts
src/pages/             LandingPage, LoginPage, SignupPage, NotFoundPage
```

## Quality floor

Keyboard-only use, 3px focus ring, skip link, labelled fields, screen-reader-announced errors, AA
contrast, ≥ 44px tap targets, no horizontal scroll at 375px, reduced motion respected. Light mode only.

## Testing

Vitest + Testing Library, test-first:

- `validation.ts` rules
- `schedule.ts`: `isInNow`, `minutesToPercent`, department filtering, with a fixed clock
- `DoctorSchedule`: "In now" tags and filter behaviour
- `LoginPage`: empty submit errors + focus, show/hide password, 401 message, network message
- `SignupPage`: mismatch, terms, email taken, success state
- `LandingPage`: hospital name from config, sign rows link to `#emergency`, `#doctors`, `#sign-in`

Then a visual check in the browser at 1280px and 375px.

## Out of scope

Staff app shell (#5), backend endpoints, password reset, terms/privacy pages, dark mode, Urdu translation.
