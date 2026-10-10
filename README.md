# Resort planner

Friends join a group through an invite link, say which resort they'll be at
on which day, see a "who's where" board, and agree where to meet. An email
the evening before sums up tomorrow.

This repository is the skeleton: project setup, the data model, tests and
CI. There are no screens yet.

## Running locally

```bash
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py import_resorts --commit   # load resorts and passes
uv run python manage.py createsuperuser
uv run python manage.py runserver                 # admin at /admin/
```

## Checks

`tox` runs everything CI runs:

```bash
uv run tox              # fmt, lint, mypy, django-checks, migrations, test
uv run tox -e test      # one env
```

## Layout

```
config/settings/   base, development, production
apps/core/         BaseModel and the share-link token helper
apps/accounts/     User, signing in with an email address
apps/resorts/      Pass, Resort, the resort sheets and import_resorts
apps/groups/       Group, Membership, PlanDay, MeetUp, MeetUpParticipant
tests/             mirrors apps/
```

See [CLAUDE.md](CLAUDE.md) for conventions.
