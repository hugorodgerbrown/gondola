# Gondola keeps its own user model

Status: accepted (2026-10-13)

## Context

Gondola was built before it was moved onto the Titan template. It has a
custom `accounts.User` (`AUTH_USER_MODEL`): signed in by email address, no
username, with a display name friends see, the evening-email switch and
when the onboarding tour was last finished. The template uses Django's
plain `auth.User`, whose username is the lowercased email.

## Decision

Keep `accounts.User`. Code taken from the template finds people with
`get_user_model()` and looks them up by email, never by `username`.

## Consequences

- No data migration: swapping `AUTH_USER_MODEL` on a live database means
  rewriting every foreign key to the user table, for no gain to anyone.
- `copier update` will show conflicts where the template's accounts code
  assumes `username`; those are resolved towards email.
- Emails are still lowercased at every entry point
  (`apps.accounts.models.normalise_email`).
