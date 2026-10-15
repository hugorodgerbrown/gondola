# Gondola keeps email addresses

Status: accepted (2026-10-15)

## Context

The Titan template now stores no email address by default: an account's
username is an HMAC of the address, keyed with `ACCOUNTS_EMAIL_KEY`, and a
masked form (`h•••@example.com`) is kept for display. An app built that way
can email someone only while they sign in. An app that has to email people
later sets `ACCOUNTS_KEEP_EMAIL`, which keeps the address as well.

Gondola emails people after they sign in: the evening-before email says
where their friends will be. It also has its own `User`, keyed on email,
with no username (gondola-keeps-its-own-user-model.md).

## Decision

Keep the address, on the account and on each sign-in request, as before.
Don't take the template's keyed addresses: no `email_key()`,
`masked_email`, `ACCOUNTS_EMAIL_KEY` or `accounts.E001` check. The privacy
notice says the address is kept and what it is used for.

## Consequences

- The database holds every member's address, so a copy of it is a mailing
  list. It is protected like the rest of the data; the notice says so.
- `copier update` will show conflicts where the template's accounts code
  uses the key or the masked address; they are resolved towards the
  address, as `username` already is.
- Turning the evening email off for good would remove the reason; revisit
  this then, with a new issue.
