# Gondola

Friends join a group through an invite link, say which resort they'll be at
on which day, and see a "who's where" board. Meeting up happens in the
group chat. An email the evening before sums up tomorrow.

## The screens

| Screen | URL | What it does |
|---|---|---|
| Front page | `/` | Explains the app; signed-in people go to the map |
| Sign in | `/sign-in/` | Emails a one-time link; no passwords. First sign-in asks for a name |
| Map | `/app/map/?date=&pass=` | Every resort as a pin, friend counts for the day, pass filter. Tap a pin for the resort sheet: who's there, plan your day here |
| Calendar | `/app/days/` | A month at a time. Tap a day for who's with you and who's elsewhere; Add plans picks a resort (friends' first, then search) |
| Groups | `/app/groups/` | Your groups; start one |
| Group | `/app/groups/<uuid>/` | Members, the invite link (share, reset), leave or delete |
| Who's where | `/app/groups/<uuid>/board/` | People down the side, 7 days across, resort codes |
| Invite | `/i/<token>/` | Readable without an account; the Join button joins |
| Account | `/app/account/` | Name, evening email, sign out, delete |
| Terms, privacy, help | `/terms/`, `/privacy/`, `/help/` | Public; the MCP tools `privacy_policy`, `terms_of_service` and `help` return the same words |

Everything signed-in lives under `/app/`, the installed app's scope
(docs/pwa.md).

## Running locally

```bash
cp .env.example .env
uv sync && npm install
uv run python manage.py migrate
uv run python manage.py import_resorts --commit             # resorts and passes
uv run python manage.py seed_demo --commit --email you@example.com  # a busy January week
uv run python manage.py seed_ui_test --commit  # "UI test"; join via Testers in the admin
uv run python manage.py runserver
```

Sign in at <http://localhost:8000/sign-in/> with the email you seeded. In
development the email prints to the console and the "check your email" page
shows the link, so no mail server is needed.

`uv run python manage.py send_evening_emails` lists who would get tomorrow's
email; add `--commit` to send.

## Deploying

`render.yaml` is a Render blueprint for the `gondola` web service, and has
no scheduled jobs for now. The app uses the existing `shared-db` Postgres
instance, in a role and database of its own (`gondola`). Send the evening
email by hand with `send_evening_emails --commit` from a Render shell.
Migrations and the resort import run before each deploy; `/livez` is
Render's health check and `/healthz` also reads the database.

Setup is [titan](https://github.com/hugorodgerbrown/django-titan-template/tree/main/titan),
installed once with `uv tool install` (its README lists the keys it reads
from 1Password):

```bash
titan status gondola   # what exists and what is missing
titan deploy gondola   # fills the env groups, links them, deploys; asks first
titan golive gondola   # after the CNAME: waits for DNS, sets SITE_URL
```

The service reads two env groups: `titan`, shared by every Titan app
(debug off, the Python version, hosts and CSRF origins under
ultraniche.ai, the SMTP relay), and `gondola`, its own (`DATABASE_URL`,
`DJANGO_SECRET_KEY`, the mail key and sender, `SITE_URL`). Only
`DJANGO_SETTINGS_MODULE` (`config.settings`) is set in `render.yaml`. To override a shared
value for Gondola alone, set it on the service, which wins over both
groups. The settings read Titan's `DJANGO_*` names as well as the bare
ones, and the host in `SITE_URL` is always allowed. On Render debug is
off unless `DJANGO_DEBUG` turns it on.

`SITE_URL` must be the address people use, because passkeys are tied to its
domain: a passkey added on `gondola.ultraniche.ai` won't work on the
`.onrender.com` address. Override with `WEBAUTHN_RP_ID` and
`WEBAUTHN_ORIGINS` only if the two must differ. If they disagree with the
address in use, the passkey endpoints answer 409 and log
`passkeys.wrong_host`.

## Checks

`tox` runs everything CI runs:

```bash
uv run tox              # fmt, lint, types, checks, test, js, audit
uv run tox -e e2e       # Playwright journeys (service worker, offline)
uv run tox -e test      # one env
uv run tox -e sast      # semgrep (downloads rule packs; CI runs it too)
```

## Layout

```
config/            settings.py (one module, env-driven), urls, wsgi/asgi
apps/core/         BaseModel, idempotency, tokens, health checks, the move to /app/
apps/public/       the front page, terms, privacy, help
apps/pwa/          manifest, service worker (/app/sw.js), offline page, launch screen
apps/accounts/     User, emailed sign-in links, the account page
apps/resorts/      Pass, Resort, the resort sheets, import_resorts, search
apps/groups/       Group, Membership, PlanDay;
                   services/ (plans, board, map, evening email), views/, send_evening_emails, seed_demo,
                   seed_ui_test
apps/tour/         the onboarding tour (docs/onboarding-tour.md)
apps/mcp/          the MCP endpoint (/mcp) and its tools; auth is mcp-auth
templates/         base.html and shared includes
static/            app.css, app.js, map.js, vendored htmx and MapLibre
tests/             mirrors apps/; tests/js holds the Vitest tests
docs/              pwa, security, performance, testing, the onboarding tour, decisions/
```

## Connecting Claude (MCP)

Gondola serves an MCP endpoint at `/mcp`, so Claude can read and change
your days: add `https://gondola.ultraniche.ai/mcp` as a custom connector
and sign in when asked. Signing in and tokens are the shared Titan
[mcp-auth](https://github.com/hugorodgerbrown/mcp-auth) app (OAuth 2.1);
any active account may connect. The tools:

| Tool | Does |
|------|------|
| `find_resort` | Resorts by part of a name or code |
| `my_days` | Your said days |
| `set_days` | Put you in one resort on some days (also how a day moves) |
| `clear_days` | Make days unsaid |
| `my_groups` | Your groups and their members |
| `whos_where` | Who's in which resort, day by day |
| `where_is` | One friend's days |
| `privacy_policy`, `terms_of_service`, `help` | The public pages, as Markdown |

Locally, mint a token for the only superuser and call it with curl
(mcp-auth 0.1.2's `--username` looks up a `username` field, which
Gondola's email-keyed `User` doesn't have):

```bash
TOKEN=$(uv run python manage.py mint_mcp_token --commit -v 0)
curl -s -X POST http://localhost:8000/mcp -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

See [CLAUDE.md](CLAUDE.md) for conventions.
