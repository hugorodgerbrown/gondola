# Security

What is on by default, and what checks it.

| Control | Where | Checked by |
| --- | --- | --- |
| HTTPS redirect, HSTS, secure cookies (when `DJANGO_DEBUG=0`) | `config/settings.py` | `tox -e checks` (`check --deploy --fail-level WARNING`) |
| CSP: this origin, plus Google Fonts, the basemap's hosts and `blob:` for the map, and `https://fiveb.ar` while `FIVEBAR_DOMAIN` is set; no inline script or style, no eval | `SECURE_CSP` | `tests/test_security.py`, `tests/core/test_analytics.py` |
| Clickjacking, sniffing, referrer, COOP headers | settings + middleware | `tests/test_security.py` |
| CSRF on every form and outbox write (token read at send time) | Django + `outbox.js` | `tests/core/test_views.py` |
| No passwords for people: sign-in by single-use emailed link, or a passkey; staff passwords are validated | `apps/accounts/` | `tests/accounts/` |
| Sign-in links are signed, expire in 30 minutes and stop working once any link is used | `apps/accounts/services.py` | `tests/accounts/test_services.py` |
| Rate limits on sign-in emails and passkey challenges | `apps/core/ratelimit.py` | `tests/accounts/test_views.py`, `test_passkeys.py` |
| Passkeys require user verification; challenges are single-use | `apps/accounts/passkeys.py` | `tests/accounts/test_passkeys.py`, `tests/e2e/test_passkey.py` |
| Post-sign-in redirects stay on this site | `apps/accounts/services.py: safe_next` | `tests/accounts/test_services.py` |
| Signing out drops cached pages on the device | `pwa.js` (`data-sign-out`) | by hand |
| Each keyed write runs at most once, per user, per body | `apps/core/idempotency.py` | `tests/core/test_idempotency.py` |
| Signed-out writes get 401, never a redirect | `login_required_json` | `tests/core/test_decorators.py` |
| Python security lint (bandit rules) | ruff `S` | `tox -e lint` |
| Static analysis: Django, Python, JS, security-audit packs | semgrep | `tox -e sast` (CI and weekly) |
| Known CVEs in runtime Python deps and npm packages | pip-audit, npm audit | `tox -e audit` (CI and weekly) |
| Secrets in commits | gitleaks | pre-commit and CI |
| Dependency updates | Dependabot (uv, npm, actions) | weekly PRs |
| MCP: OAuth 2.1, PKCE, audience-bound tokens; any active account, acting only as itself through its groups | `mcp-auth`, `apps/mcp/` | `tests/mcp/` |
| Group-mates only: a person's friends are found through `Group.objects.for_user`, which hides demo groups | `apps/groups/` | `tests/groups/`, `tests/tour/` |

## Invariants

1. No `mark_safe()` or `|safe` on anything that came from outside the code.
   A template variable in an `href` is marked `nosemgrep` with why it is safe.
2. No secrets in source: everything through `python-decouple`; `.env` is
   gitignored.
3. No inline script, style or event handler in a template (emails aside:
   mail clients need inline styles).
4. Every outbox endpoint is `@login_required_json`. A sheet fragment asked
   for without htmx gets a whole page (`apps/core/http.py`).
5. A sign-in link is never logged.
6. Who may connect an MCP client (`MCP_AUTH` in `config/settings.py`) is a
   product decision, changed only in a PR that says so.
