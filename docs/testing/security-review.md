# Security review (#58)

**Date:** 2026-11-22 · **Bolt:** B13

## Deployment checks

With `DJANGO_DEBUG=false`, `python manage.py check --deploy --fail-level WARNING` reports no issues.
`apps/core/tests/test_security.py::test_check_deploy_is_clean_with_production_settings` runs it on every CI build.

Added in `backend/config/settings.py` (production only, env-overridable):

| Setting | Value | Why |
|---|---|---|
| `SECURE_SSL_REDIRECT` | on (`SECURE_SSL_REDIRECT=false` to disable) | HTTPS only |
| `SECURE_REDIRECT_EXEMPT` | `^api/health/$` | Render's health check calls over plain HTTP |
| `SECURE_HSTS_SECONDS` | 30 days (`SECURE_HSTS_SECONDS`) | Browsers keep using HTTPS |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | on | `check --deploy` |
| Already present | secure + SameSite=None session and CSRF cookies, `SECURE_PROXY_SSL_HEADER` | cross-site session (Vercel → Render) |

## Permission review

`apps/core/tests/test_security.py::test_every_api_view_names_a_role_based_permission` walks every `/api/` URL and
fails if a view is open to anyone or only checks sign-in, unless it's on a commented allow-list:

| Group | Views | Why it's allowed |
|---|---|---|
| Public | health, login, logout, signup, CSRF, public ER status | Needed before sign-in |
| Signed-in only | `MeView` | The user's own account |
| Checked per resource type | `HeldReservationListView`, `ReservationAllocateView`, `ReservationAllocateManyView` | The rule depends on the type in the request; the view and services check `can_see` / `can_edit` on that type's module plus `own_hospital` |

Every other endpoint uses `module_permission("<module>")` from `apps/accounts/permissions.py`, the same table the
frontend uses (`frontend/src/features/staff/roles.ts`); the two are compared by `roles.test.ts` and documented in
`docs/architecture/api-contracts.md`. Own-hospital rules (`own_hospital`, `may_change`) are applied in the views and
services that change hospital-owned rows.

## Open items

- Rate limiting on login exists (`test_login_security.py`); no general API rate limit. Not needed for the MVP.
- Rotate `DJANGO_SECRET_KEY` on staging if it was ever shared outside Render.
