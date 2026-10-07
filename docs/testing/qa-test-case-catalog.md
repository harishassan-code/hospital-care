# QA test case catalog (adapted to current frontend)

| | |
|---|---|
| **Source sheets** | [login-positive-test-cases.md](source/login-positive-test-cases.md) · [carelink-negative-test-cases.md](source/carelink-negative-test-cases.md) |
| **Current app** | Public home `/` · Sign-in `/login` · Staff workspace `/staff/*` · Django session cookies + CSRF |
| **Automation** | Vitest + Testing Library in `frontend/src/qa/` (ids kept in test names) |
| **Execution report** | [authentication-test-report.md](authentication-test-report.md) |

**How to read “Automation”:** ✅ Vitest · 📷 Manual / Playwright screenshots · 🔧 Backend pytest · ⏳ Planned · ➖ N/A on this install

---

## A. Sign-in — positive (TC-01 … TC-30)

| ID | Title | Steps (summary) | Expected (original sheet) | Expected (Northgate app today) | Automation |
|---|---|---|---|---|---|
| TC-01 | Login / entry loads | Open app URL | Login page with all elements | Public home loads (`LandingPage`); **Log in** → `/login` with **Sign in** heading | ✅ `login.qa.test.tsx` |
| TC-02 | Required UI elements | Observe login page | Logo, fields, Login, Forgot, Remember me | Hospital link, Email, Password, **Log in**, **Forgot your password?**; no Remember me (server session) | ✅ `login.qa.test.tsx` |
| TC-03 | Valid staff login | Enter credentials → Login | Redirect to hospital dashboard | Staff → `/staff` (Overview) | ✅ |
| TC-04 | Button / empty fields | Fill or leave empty | Login enabled when both filled | **Log in** always enabled; empty submit shows field errors; **no POST** | ✅ |
| TC-05 | Password masked | Type password | Dots/asterisks | `type="password"` | ✅ |
| TC-06 | Show/hide password | Toggle show | Plain text then masked again | Show / Hide password buttons | ✅ |
| TC-07 | Remember me | Check remember → reopen browser | Credentials remembered | Session in **HttpOnly cookie**; `localStorage` / `sessionStorage` empty after login | ✅ |
| TC-08 | Valid email format | user@hospital.com | Login succeeds | Valid email accepted; POST `/api/auth/login/` | ✅ |
| TC-09 | Username without @ | Enter username | Login succeeds if supported | **Rejected** before POST: “Enter an email like name@example.com” | ✅ 🔁 |
| TC-10 | Tab order | Tab through fields | email → password → remember → login | email → password → Show → Forgot help → Log in | ✅ 🔁 |
| TC-11 | Enter submits | Enter in password field | Login submitted | Enter submits; lands on `/staff` | ✅ |
| TC-12 | Special characters in password | P@ssw0rd! etc. | Login succeeds | Password sent **exactly** as typed; email trimmed | ✅ |
| TC-13 | Forgot password link | Click link | Password reset page | Inline help: ask front desk / administrator | ✅ 🔁 |
| TC-14 | Role-based landing | Login as each role | Each role’s dashboard | All staff → `/staff`; **patient** → `/` | ✅ |
| TC-15 | Session token/cookie | Inspect storage after login | Token/cookie created | Session cookie via `credentials: 'include'`; no token in JSON body | ✅ 🔁 |
| TC-16 | Responsive layout | Mobile / tablet widths | Usable layout | No horizontal scroll at 375px (see report §5 screenshots 13–14) | 📷 |
| TC-17 | Browser autofill | Open login | Fields populate | `autocomplete="username"` + `current-password` | ✅ |
| TC-18 | Loading indicator | Submit valid login | Spinner while waiting | Button **Logging in…** and disabled | ✅ |
| TC-19 | Cross-browser | Chrome, Firefox, Edge | Consistent layout | Same React app; spot-check in demo | 📷 |
| TC-20 | Logout → login | Logout from dashboard | Back at login | **Sign out** → POST logout → sign-in page | ✅ `staff-workspace.qa.test.tsx` LAND-N08 |
| TC-21 | Admin module access | Login as admin | Register Hospital / Manage Users | Admin → `/staff` with **all** nav modules | ✅ + 📷 screenshot 11 |
| TC-22 | Cross-hospital data scope | Staff of hospital A | Only A’s data | **One hospital per install** — no cross-hospital API | ➖ |
| TC-23 | Coordinator → emergency | Coordinator login | Emergency request screen | Emergency module **Sprint 5** | ⏳ `it.todo` in `login.qa.test.tsx` |
| TC-24 | Audit log on login | Login then view audit | LOGIN_SUCCESS entry | Audit trail **not in UI yet** | 🔧 backend when FR-14 ships |
| TC-25 | Session timeout (30 min) | Idle 30+ min | Re-login required | Server session expiry — verify in integration | 🔧 `test_login_security.py` |
| TC-26 | Success after one failure | 2nd attempt correct password | Login succeeds | Lockout only after **5** failures (N03) | ✅ implied by N03 tests |
| TC-27 | Email reset → login | Reset link → new password | Login with new password | Self-service reset **not built** | ⏳ |
| TC-28 | Concurrent sessions | Login on device B while A active | Policy-consistent | Single-server session store; multi-device manual check | 📷 optional |
| TC-29 | Deep link after login | Open `/staff/beds` logged out | Return to requested page | `?next=` → safe internal path only; blocks external URLs | ✅ |
| TC-30 | Login API contract | POST login, inspect JSON | 200 + token, role, hospital id | 200 + **user + role**; session cookie; no JWT in body | ✅ |

---

## B. Sign-in — negative (LOGIN-N01 … LOGIN-N15)

| ID | Severity | Title | Expected (sheet) | Expected (Northgate app today) | Automation |
|---|---|---|---|---|---|
| LOGIN-N01 | Critical | Unknown email | Generic invalid credentials | Same generic alert; no “unknown email” wording | ✅ |
| LOGIN-N02 | Critical | Wrong password | Same message as N01 | Same generic alert | ✅ |
| LOGIN-N03 | Critical | Brute-force lockout | Lock or throttle after 5–10 tries | **429** after 5 failures / 15 min message | ✅ + 🔧 backend |
| LOGIN-N04 | Critical | SQL injection | Reject; no bypass | Malformed **email** blocked client-side; API tests injection payloads | ✅ + 🔧 |
| LOGIN-N05 | High | XSS in fields | Escaped; no script run | React text nodes; test sets `window.__xss` guard | ✅ |
| LOGIN-N06 | High | Empty fields | Client + server block | All-empty / one-empty; no POST | ✅ |
| LOGIN-N07 | High | Deactivated account | “Account disabled” | **Generic** message (no account enumeration) | ✅ 🔁 |
| LOGIN-N08 | Critical | Role tampering | Server rejects escalated role | Role from `/auth/me/` only; 403 on forbidden APIs | 🔧 RBAC tests |
| LOGIN-N09 | Medium | Token after logout | 401 on replay | Session invalidated on logout | 🔧 backend session tests |
| LOGIN-N10 | Medium | Revoked session on device A | A logged out on next request | Same as N09 when session revoked | 🔧 |
| LOGIN-N11 | High | Password masking | type=password; HTTPS | Masked; HTTPS in staging | ✅ (= TC-05) |
| LOGIN-N12 | Medium | Case / whitespace | Email trimmed, case-insensitive; password exact | Trim email on send; password not trimmed | ✅ |
| LOGIN-N13 | High | CSRF on login | Reject third-party origin | POST requires CSRF cookie + header | 🔧 backend |
| LOGIN-N14 | Medium | Oversized input | Graceful length error | Email ≤254, password ≤512; no POST | ✅ |
| LOGIN-N15 | Critical | API role/hospital injection | Server ignores client role/hospital | Body keys **only** `email`, `password` | ✅ |

---

## C. Main landing / staff workspace — negative (LAND-N01 … LAND-N10)

In the sheet, “landing” is the **post-login dashboard**. In this app that is the **staff workspace** (`/staff`).

| ID | Severity | Title | Expected (sheet) | Expected (Northgate app today) | Automation |
|---|---|---|---|---|---|
| LAND-N01 | Critical | Direct URL without auth | Redirect login; no data leaked | `/staff` → sign-in; `?next=` preserved | ✅ |
| LAND-N02 | Critical | Cross-hospital leakage | No other hospital’s data | Single-hospital install | ➖ |
| LAND-N03 | High | Wrong role widgets | City command hidden | Nav + routes restricted; direct URL → **no access** | ✅ |
| LAND-N04 | High | API down / timeout | Per-widget error; no white screen | ER tile error; other tiles still load; total outage message | ✅ |
| LAND-N05 | Medium | Idle session expiry | Re-auth on refresh | Session timeout — backend | 🔧 / 📷 |
| LAND-N06 | Medium | Broken nav links | No 404 / dead links | Overview, Beds, Blood, Pharmacy routes exist | ✅ |
| LAND-N07 | High | Stored XSS in data | Escaped output | Ward name HTML shown as text | ✅ |
| LAND-N08 | Medium | Back button after logout | No cached live data | Logout clears server session; revisit → sign-in | ✅ |
| LAND-N09 | Medium | Zero counts | Show **0**, not blank/NaN | Beds 0 of N; ER 0 waiting | ✅ |
| LAND-N10 | Medium | Mobile layout | No overlap / horizontal scroll | Staff + login mobile screenshots | 📷 |

---

## D. Public home (companion to TC-01)

Not in the original negative sheet as its own module; covered because TC-01 entry is the **public** landing.

| ID | Title | Steps | Expected | Automation |
|---|---|---|---|---|
| PUB-01 | Public home content | Open `/` | Hospital name, wayfinding, ER status, tel link | ✅ `LandingPage.test.tsx` |
| PUB-02 | Public status failure | API down for `/public/status/` | “Live status isn’t available right now” | ✅ `LandingPage.test.tsx` |

---

## E. Running the automated QA suite

```bash
cd frontend && npm test -- src/qa
```

For full evidence (screenshots, pytest, mutation check), see [authentication-test-report.md](authentication-test-report.md).
