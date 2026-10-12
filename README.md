# Gondola

Friends join a group through an invite link, say which resort they'll be at
on which day, see a "who's where" board, and agree where to meet. An email
the evening before sums up tomorrow.

## The screens

| Screen | URL | What it does |
|---|---|---|
| Front page | `/` | Explains the app; signed-in people go to the map |
| Sign in | `/sign-in/` | Emails a one-time link; no passwords. First sign-in asks for a name |
| Map | `/map/?date=&pass=` | Every resort as a pin, friend counts for the day, pass filter. Tap a pin for the resort sheet: who's there, plan my day here, propose a meet-up |
| My days | `/days/` | The next 14 days. Tap a day: skiing / not sure yet / not skiing, friends' resorts first, search, note, private |
| Groups | `/groups/` | Your groups; start one |
| Group | `/groups/<uuid>/` | Members, the invite link (share, reset), leave or delete |
| Who's where | `/groups/<uuid>/board/` | People down the side, 7 days across, resort codes, the meet-up row |
| Invite | `/i/<token>/` | Readable without an account; the Join button joins |
| Propose a meet-up | `/groups/<uuid>/meetups/new/` | Ranked suggestions, another resort, optional time and meeting pin |
| Meet-up | `/m/<token>/` | Public page that unfurls in a group chat; going sets your day |
| Account | `/account/` | Name, evening email, sign out, delete |

## Running locally

```bash
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py import_resorts --commit             # resorts and passes
uv run python manage.py seed_demo --commit --email you@example.com  # a busy demo group
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

The one-click setup is `bin/titan` in
[django-titan-template](https://github.com/hugorodgerbrown/django-titan-template)
(its README lists the keys it needs). From a checkout of the template, next
to this one:

```bash
bin/titan new gondola              # plan: changes nothing
bin/titan new gondola --commit     # stops once for the Blueprint, then:
                                   # database, Resend key, env vars, domain, deploy
bin/titan golive gondola           # prints the CNAME to add
bin/titan golive gondola --commit  # waits for DNS, sets SITE_URL
```

The repository already exists, so `new` skips generating it. There is no
`gondola-purge` cron job, so `bin/titan` provisions the web service alone.
The settings read Titan's `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` and
`DJANGO_DEBUG` as well as the bare names, and the host in `SITE_URL` is
always allowed.

`SITE_URL` must be the address people use, because passkeys are tied to its
domain: a passkey added on `gondola.ultraniche.ai` won't work on the
`.onrender.com` address. Override with `WEBAUTHN_RP_ID` and
`WEBAUTHN_ORIGINS` only if the two must differ. If they disagree with the
address in use, the passkey endpoints answer 409 and log
`passkeys.wrong_host`.

## Checks

`tox` runs everything CI runs:

```bash
uv run tox              # fmt, lint, mypy, django-checks, migrations, test
uv run tox -e test      # one env
```

## Layout

```
config/settings/   base, development, production
apps/core/         BaseModel, tokens, the front page, manifest and service worker
apps/accounts/     User, emailed sign-in links, the account page
apps/resorts/      Pass, Resort, the resort sheets, import_resorts, search
apps/groups/       Group, Membership, PlanDay, MeetUp, MeetUpParticipant;
                   services/ (plans, board, suggestions, meet-ups, map,
                   evening email), views/, send_evening_emails, seed_demo,
                   seed_ui_test
templates/         base.html and shared includes
static/            app.css, app.js, map.js, vendored htmx and MapLibre
tests/             mirrors apps/
```

See [CLAUDE.md](CLAUDE.md) for conventions.
