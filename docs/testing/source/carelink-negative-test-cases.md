# CareLink - Negative Test Cases

Login System + Main Landing Page · QA Test Suite

Critical High Medium

## Module 1: Login System

LOGIN-N01Critical

Login with invalid email/username and valid password

**Precondition:** A registered hospital staff account exists.

**Steps:** Enter an unregistered email + correct-format password, submit.

**Expected:** Generic "invalid credentials" error shown. System must NOT reveal whether the email exists (prevents account enumeration of hospital staff).

LOGIN-N02Critical

Login with valid email and incorrect password

**Steps:** Enter a known valid hospital staff email with a wrong password.

**Expected:** Same generic error as LOGIN-N01 (identical wording/response time) so the two failure cases are indistinguishable.

LOGIN-N03Critical

Brute-force / account lockout enforcement

**Steps:** Submit 5-10 consecutive wrong-password attempts for the same account.

**Expected:** Account locks temporarily or CAPTCHA/throttling is triggered. Login attempts for an emergency-critical account should never allow unlimited guessing given how sensitive patient-resource data is.

LOGIN-N04Critical

SQL injection in email/password fields

**Steps:** Enter payloads such as `' OR '1'='1` or `admin'--` in both fields.

**Expected:** Login rejected with standard invalid-credentials error; no database error leaked; no authentication bypass into any hospital or city admin account.

LOGIN-N05High

XSS payload in login fields

**Steps:** Enter `<script>alert(1)</script>` into email field, submit.

**Expected:** Input is sanitized/escaped; script does not execute; error message renders the text as plain text, not HTML.

LOGIN-N06High

Empty field submission

**Steps:** Submit the form with email blank, password blank, and both blank.

**Expected:** Client-side and server-side validation both block submission with field-specific inline errors; no network request with empty credentials reaches the backend unvalidated.

LOGIN-N07High

Login as a disabled/deactivated hospital account

**Precondition:** A hospital admin has deactivated a staff account (e.g. employee left).

**Steps:** Attempt login with the deactivated account's correct credentials.

**Expected:** Login rejected with an "account disabled" message; no session/token issued; no residual dashboard access.

LOGIN-N08Critical

Role tampering via manipulated token/response

**Steps:** Log in as Hospital Staff, then intercept/modify the session token or local storage role claim to "City Administrator".

**Expected:** Backend re-validates role server-side on every request; tampered client-side role is rejected, user cannot escalate to city-wide data access.

LOGIN-N09Medium

Expired session / token reuse after logout

**Steps:** Log in, log out, then replay the old session token/cookie directly against an API endpoint (e.g. view blood inventory).

**Expected:** Request is rejected with 401/403; the invalidated token grants no further access.

LOGIN-N10Medium

Concurrent session from a second device while token is revoked on the first

**Steps:** Log in on Device A, then have an administrator force-revoke the session (e.g. after reporting a compromised device).

**Expected:** Device A is logged out on next request; cannot continue reserving/releasing resources with the revoked session.

LOGIN-N11High

Password field exposes plaintext or weak masking

**Steps:** Inspect the password input's type attribute and network payload.

**Expected:** Field is masked (type=password); password is never sent or logged in plaintext over an insecure channel; HTTPS enforced.

LOGIN-N12Medium

Case sensitivity and whitespace handling

**Steps:** Enter valid email with mixed case and trailing/leading spaces; enter valid password with an unintended trailing space.

**Expected:** Email is treated case-insensitively and trimmed; password is treated as case-sensitive and NOT trimmed (so a password differing only by whitespace correctly fails).

LOGIN-N13High

CSRF protection on login form

**Steps:** Submit the login request from a third-party origin without a valid CSRF token/header.

**Expected:** Request is rejected; login only succeeds from the legitimate CareLink origin.

LOGIN-N14Medium

Oversized input in credential fields

**Steps:** Paste a 10,000+ character string into the email and password fields and submit.

**Expected:** Input is rejected gracefully with a length-validation error; no server crash, timeout, or unhandled exception.

LOGIN-N15Critical

Direct API login bypass (skipping UI)

**Steps:** Send a crafted POST request directly to the authentication endpoint with a role or hospital_id parameter manually injected (e.g. claiming to belong to a hospital the user wasn't registered under).

**Expected:** Server derives role and hospital association from the authenticated record only, ignoring any client-supplied role/hospital_id in the request body.

---

## Module 2: Main Landing Page

LAND-N01Critical

Direct URL access to dashboard without authentication

**Steps:** While logged out, paste the direct dashboard/landing URL into the browser address bar.

**Expected:** Redirected to login; no hospital resource data (beds, blood units, ICU counts) is rendered or present in the page source/network response before redirect.

LAND-N02Critical

Cross-hospital data leakage on landing page

**Precondition:** User belongs to Hospital A.

**Steps:** Load the landing page, inspect all API calls/JSON payloads returned, including ones not shown in the UI.

**Expected:** No resource, staff, or patient data belonging to Hospital B, C, or D is returned in any response, even if hidden from the visible UI.

LAND-N03High

Role-restricted widgets visible to wrong role

**Steps:** Log in as Hospital Staff (not City Administrator) and check for presence of the city-wide command center widget or link.

**Expected:** City-wide elements are not rendered and not reachable by guessing the route; backend also blocks the underlying API for this role.

LAND-N04High

Landing page behavior when backend/resource API is unavailable

**Steps:** Simulate the resource-availability API timing out or returning a 500 error, then load the landing page.

**Expected:** Page degrades gracefully with an error/loading state per widget (e.g. "unable to load blood availability"); it does not crash, show stale data as if current, or display a blank white screen.

LAND-N05Medium

Session expiry while idle on the landing page

**Steps:** Log in, leave the landing page idle past the session timeout, then trigger a data refresh/action.

**Expected:** User is prompted to re-authenticate; no stale resource counts are treated as live, and no reservation/emergency action can be submitted on an expired session.

LAND-N06Medium

Broken or placeholder links on landing page

**Steps:** Click every navigation link/button (emergency request, blood, beds, equipment, operating rooms, notifications icon).

**Expected:** No 404s, no dead links, no console errors; each link routes to a built or clearly marked "coming soon" (advanced/second-increment) section rather than failing silently.

LAND-N07High

Stored XSS via displayed hospital/resource data

**Precondition:** A hospital name, department, or equipment note field contains a script payload (e.g. entered during a prior data-entry test).

**Steps:** Load the landing page where that field is rendered (e.g. hospital name in dashboard header).

**Expected:** Payload is rendered as escaped text, not executed; confirms resource/hospital fields are sanitized on output, not just on input.

LAND-N08Medium

Browser back button after logout

**Steps:** Log in, view the landing page, log out, then press the browser's back button.

**Expected:** Cached landing page is not shown with live data; app detects invalid session and forces redirect to login (cache-control headers prevent sensitive data from being served from browser cache).

LAND-N09Medium

Zero/negative resource counts rendering

**Precondition:** A hospital has 0 available ICU beds and 0 blood units of a given type.

**Steps:** Load the landing page for that hospital.

**Expected:** Counts display accurately as 0 (not blank, not negative, not "undefined"/"NaN"); zero-availability is visually flagged, not treated as a loading error.

LAND-N10Medium

Responsive layout breakage on small screens

**Steps:** Load the landing page on a narrow mobile viewport (e.g. 360px width).

**Expected:** No horizontal page scroll, no overlapping widgets, resource tables scroll within their own container; all critical counts remain readable.

CareLink QA · Negative Test Suite · Login System + Landing Page