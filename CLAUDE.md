# CLAUDE.md — Gondola

A standalone Django app for friends to see who's skiing where. It started as a
Snowdesk feature and was split out on purpose: it shares Snowdesk's tooling
and conventions, not its code or database.

It is a Titan app: it follows the
[django-titan-template](https://github.com/hugorodgerbrown/django-titan-template)
(`.copier-answers.yml`), so `copier update --trust` pulls in template fixes.
Keep shared files close to the template so that stays a clean merge; where
Gondola differs on purpose, the reason is in `docs/decisions/`.

The product name users see is `SITE_NAME` ("Gondola"). The repository,
Python package, Render service and database are all named `gondola` too;
it lives at <https://gondola.ultraniche.ai>.

Python 3.14 / Django 6.1, pinned in `pyproject.toml`.

## Product decisions already made

- Group members see each other's names and days. Joining is the consent.
- An invite link joins at once. The owner can reset it, which kills the old
  link. Opening the link never joins by itself: a Join button does.
- Gondola is for planning ahead: who's in which resort over the coming
  days and weeks. Whether anyone is skiing tomorrow is for the group chat.
- A plan day belongs to a person, not a group, and group-mates see every
  day said. There are no private days: someone who doesn't want to be
  found doesn't say where they are.
- A plan day answers one question: which resort you'll be in. There is no
  skiing yes/no, no "not sure" and no "no resort": an unsaid day is the
  undecided one, and a missing resort gets added to the sheet.
- A sheet for several days puts them all in one resort.
- The calendar shows you by default. Its chips pick one of your groups,
  which only adds pale days: where that group's people will be on the days
  you haven't said. Your own days never change.
- Meet-ups are not in the app: friends agree them in their group chat.
- Touring spots are not resorts and are never imported.
- New accounts are offered a look-and-tap tour of a private demo group
  (docs/onboarding-tour.md). Nothing is saved in the demo, and demo groups
  never show outside it.
- Every resort is Swiss, so dates and times are Swiss wall-clock
  (`TIME_ZONE = "Europe/Zurich"`).

## Layout

```
config/          settings (one module, env-driven), urls, wsgi/asgi
apps/core/       BaseModel, IdempotencyMiddleware + IdempotencyRecord,
                 decorators (require_htmx, login_required_json), rate
                 limits, tokens, analytics (fivebar goals), livez,
                 healthz and the CSRF failure page
apps/public/     the public pages: /, /terms/, /privacy/, /help/; the terms,
                 privacy and help bodies are each one _<name>_body.html,
                 also served as Markdown (the MCP tools)
apps/pwa/        /app/manifest.webmanifest, /app/sw.js, /app/offline/;
                 conf.py holds the app's identity, SCOPE and the precache list
apps/accounts/   Gondola's own User (docs/decisions/), sign-in by emailed
                 link and code (docs/accounts.md), passkeys, the account page
apps/resorts/    the Swiss resorts, imported from apps/resorts/data
apps/groups/     groups, plan days, the calendar, board and map
apps/tour/       the onboarding tour on a private demo group
apps/mcp/        the MCP endpoint (/mcp) and its tools; auth is mcp-auth
apps/design/     the design page (/app/design/, staff only): every token
                 and every component state (DESIGN.md)
templates/       base.html (the app, /app/), public_base.html, includes
static/js/       plain JavaScript, classic scripts, no build step
static/css/      app.css: the design system, tokens on :root and
                 components below (DESIGN.md)
docs/            accounts, pwa, security, performance, testing,
                 onboarding-tour, decisions/
.claude/skills/  writing the Titan docs kept in Linear (research, user
                 testing script, blog post), each with a length setting
```

## Commands

```bash
uv sync && npm install
uv run python manage.py runserver
uv run tox                      # every check CI runs (except e2e, sast)
uv run tox -e e2e               # Playwright journeys
uv run pytest tests/groups      # targeted run while iterating
```

Never run a bare `pytest`; use `uv run`. Dependencies: `uv add` /
`uv add --group <test|lint|types|e2e> …`, then commit `uv.lock`.

## Code conventions

- A module docstring on every module and a docstring on every class and
  function (ruff `D`, Google style; test functions are exempt); every
  argument typed except `*args` / `**kwargs`.
- British English spellings, except third-party identifiers.
- `ruff` for lint and format; `pre-commit` runs it on commit.
- Simple over clever; no abstraction until two callers need it.
- `logging.getLogger(__name__)` in every module; no `print`.
- Settings: one `config/settings.py`; anything that differs per
  environment is an env var read with `python-decouple`, never hard-coded.
- Email addresses are lowercased before storage and lookup, at every entry
  point (`apps.accounts.models.normalise_email`).
- No Django signals for side effects: call them inline from the service.
- Share and invite tokens come from `apps.core.tokens.make_token`.
- Find a person's groups (and so their friends) through
  `Group.objects.for_user`: it is what shows the demo copy while they tour
  and hides demo groups otherwise. Querying memberships directly leaks one.
- The MCP endpoint is `/mcp` (`apps/mcp`, from the Titan template); auth
  is the shared `mcp-auth` app, pinned to a tag. A tool runs as the
  token's user and reaches people only through their groups (`friend_ids`,
  `Group.objects.for_user`). Any active account may connect
  (`mcp_auth.policy.active_user`).
- Product analytics are fivebar goals: queue one with
  `apps.core.analytics.record`, or `data-tally` on a clicked element.

### Views and templates

- Signed-in pages live under `/app/` (the installed app's scope) and
  extend `base.html`; public pages (front page, sign-in, invite links)
  sit outside it and extend `public_base.html`. Read
  [docs/pwa.md](docs/pwa.md#scope).
- No inline `<script>`, `style=` or `on*=` in templates (emails aside): the
  CSP blocks them and `tests/test_security.py` fails the build.
- Follow [DESIGN.md](DESIGN.md) on every UI change: check the design
  page (`/app/design/`, staff only) first, use tokens and never raw
  values, show every new component and state on the page, and delete dead
  CSS. `tests/test_design.py` enforces it.
- Add any new static file the shell needs offline to
  `apps/pwa/conf.py: PRECACHE_STATIC` (it has a byte budget).

### Models

Every concrete model ships the full kit: inherits
`apps.core.models.BaseModel`; has an explicit admin class, an explicit
`to_string()` (`__str__` delegates to it), an explicit `Meta.ordering`, a
custom queryset, a factory in `tests/factories.py`, and tests. Use `uuid`,
never `id`, in URLs and anything a client sees.

### Management commands

Run with no arguments, change nothing without `--commit`, respect
`--verbosity`, and exit non-zero on any failure.

## Tests

pytest + FactoryBoy (`tests/` mirrors `apps/`), Vitest for `static/js`
(`tests/js/`), and a small, capped Playwright suite for the service worker
and offline (`tests/e2e/`). Coverage floor 90%. Call factories with
`.create()`, never `Factory(...)`. All datetimes carry `tzinfo`. Full
rules: [docs/testing.md](docs/testing.md).

## Before opening a PR

Run `uv run tox` and fix every failure; it is exactly what CI runs.
Record a non-obvious architectural choice in `docs/decisions/`.

## Dependencies

`uv` only (`uv add`, `uv add --group …`). `pyproject.toml` is the source of
truth and `uv.lock` the pin; commit both. Tool dependencies go in the
matching `[dependency-groups]` entry (`test`, `lint`, `types`, `e2e`).
JavaScript test tooling is in `package.json` (`npm install`).
