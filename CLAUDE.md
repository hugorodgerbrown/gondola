# CLAUDE.md — Gondola

A standalone Django app for resort meet-ups among friends. It started as a
Snowdesk feature and was split out on purpose: it shares Snowdesk's tooling
and conventions, not its code or database.

The product name users see is `SITE_NAME` ("Gondola"). The repository,
Python package, Render service and database are all named `gondola` too
(the database `gondola`, since Postgres names read better without hyphens);
it lives at <https://gondola.ultraniche.ai>.

Python 3.14 / Django 6.0, pinned in `pyproject.toml`.

## Product decisions already made

- Group members see each other's names and days. Joining is the consent.
- An invite link joins at once. The owner can reset it, which kills the old
  link. Opening the link never joins by itself: a Join button does.
- A plan day belongs to a person, not a group. A day can be marked private,
  and then group-mates see nothing for it.
- A plan day answers two separate questions: where you'll be (a resort,
  or none) and whether you're skiing (yes, not sure yet, no). Someone at a
  resort who isn't skiing is "around": counted on the map, but not used to
  pick a meet-up resort. Every answer is distinct from saying nothing.
- A sheet for several days changes only the answers you touch.
- A meet-up needs a resort; the time and meeting pin are optional.
- Touring spots are not resorts and are never imported.
- Every resort is Swiss, so dates and times are Swiss wall-clock
  (`TIME_ZONE = "Europe/Zurich"`).

## Conventions

- Header comment on every module, docstring on every function and class,
  every argument typed except `*args` / `**kwargs`.
- British English spellings, except third-party identifiers.
- `ruff` for lint and format; `pre-commit` runs it on commit.
- Settings: `config/settings/base.py` plus `development.py` and
  `production.py`. Secrets via `python-decouple`, never hard-coded.
- Email addresses are lowercased before storage and lookup, at every entry
  point (`apps.accounts.models.normalise_email`).
- No Django signals for side effects: call them inline from the service.
- Share and invite tokens come from `apps.core.tokens.make_token`.

### Models

Every concrete model ships the full kit:

- inherits `apps.core.models.BaseModel`;
- an explicit admin class;
- an explicit `to_string()` (`__str__` delegates to it);
- an explicit `Meta.ordering`;
- a custom queryset;
- a factory in `tests/factories.py` and test coverage.

### Management commands

Run with no arguments, change nothing without `--commit`, respect
`--verbosity`, and exit non-zero on any failure.

### Testing

- pytest + FactoryBoy; `tests/` mirrors `apps/`. Coverage target 90%.
- Call factories with `.create()`, never `Factory(...)`.
- All datetimes carry `tzinfo`.
- Run `uv run tox` before opening a PR; it is exactly what CI runs.

## Dependencies

`uv` only (`uv add`, `uv add --dev`). `pyproject.toml` is the source of
truth and `uv.lock` the pin; commit both. Tool dependencies go in the
matching `[dependency-groups]` entry (`test`, `type`, `lint`).
