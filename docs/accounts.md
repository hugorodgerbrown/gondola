# Accounts: email sign-in and passkeys

There are no passwords. Someone signs in, and signs up, with an email
address; once in, they can add a passkey from the account page and sign in
with Face ID, a fingerprint or a device PIN from then on. Ported from the
Titan template; the differences are at the bottom.

```
                 ┌──────────── /sign-in/ ────────────┐
                 │  email ──▶ SignInRequest (hashes)  │──▶ email: link + 6-digit code
                 │  passkey button                    │
                 └──────┬─────────────────────┬──────┘
          link, any browser                code, this browser only
  /sign-in/link/<token>/ ── Continue (POST)    /sign-in/code/ ── POST code
                 └──────────────┬──────────────┘
                     used once ─▶ account found or created ─▶ login()
                                                   │
                     no name yet? ─▶ /app/welcome/ ─▶ passkey nudge ─▶ tour offer ─▶ next
                     named        ─▶ next (or the map)

 /app/account/ ── Add a passkey ─▶ options (challenge in session) ─▶ create() ─▶ verify, save Passkey
 /sign-in/     ── passkey       ─▶ options (challenge in session) ─▶ get()    ─▶ verify, login()
```

## Pieces

| File | Job |
| --- | --- |
| `apps/accounts/sign_in.py` | Issue a request; redeem its link or code once; find or create the account |
| `apps/accounts/passkeys.py` | WebAuthn options and verification (py_webauthn) |
| `apps/accounts/views.py` | Sign-in, code, link, welcome, sign-out, account and passkey endpoints |
| `apps/accounts/tasks.py` | `send_sign_in_email`, enqueued by the view (`django.tasks`) |
| `apps/accounts/models.py` | `User`, `SignInRequest`, `Passkey`, `ReviewerAccount` |
| `apps/accounts/services.py` | The evening email's opt-out link |
| `apps/core/redirects.py` | `safe_next`: only same-site paths survive |
| `static/js/passkeys.js`, `webauthn_json.js` | The browser side of both ceremonies |
| `static/js/code_input.js` | The code as six digit boxes; a pasted or autofilled code fills them all |
| `apps/core/ratelimit.py` | Cache-backed limits on emails, codes and passkey challenges |

## Signing in by email

- **One flow for both.** The first redeemed link or code for an address
  creates the account (the lowercased address, no usable password, no name
  yet). Nothing about an address is stored before then except the pending
  request.
- **The address is kept.** Gondola emails people after they sign in (the
  evening email), so the account and the request hold the lowercased
  address. It doesn't take the template's keyed addresses, and needs no
  `ACCOUNTS_EMAIL_KEY`. Why: docs/decisions/gondola-keeps-email-addresses.md.
- **Link and code, either once.** Each email carries a link and a six-digit
  code, valid for `SIGN_IN_MAX_AGE_SECONDS` (30 minutes). Asking again ends
  the earlier request, so only the newest email works. Only hashes are
  stored: the link token as SHA-256, the code as an HMAC with the secret key.
- **Why a code too.** An app installed on an iPhone home screen keeps its
  own cookies, separate from Safari. A link opened from Mail signs in
  Safari, not the app; the app's user types the code instead. The code is
  also in the email's subject, so it shows in the notification.
- **The code only works where it was asked for.** The session holds the
  request's uuid, so a code is useless in another browser, and five wrong
  codes (`SIGN_IN_MAX_CODE_ATTEMPTS`) end it. That is what makes six digits
  enough.
- **Six boxes, one field.** `code_input.js` shows the code as six digit
  boxes: typing moves on, Backspace goes back, and pasting the code (or
  iPhone's one-time-code autofill) into any box fills all six and submits.
  Underneath it is still the one `code` field, which is all a browser
  without JavaScript sees.
- **The link page needs a click.** Mail scanners open links to check them;
  a link that signed in on GET would be used up before the person saw it.
- **No enumeration.** The form answers the same whether or not the address
  has an account. A switched-off account is told so only after it proves it
  owns the address.
- **Limits.** 10 sign-in emails per IP per 10 minutes, 5 per address per
  hour, 20 code tries per IP per 10 minutes, 30 passkey challenges per IP
  per 10 minutes. Behind Render the client IP is the last `X-Forwarded-For`
  hop (`RATE_LIMIT_PROXY_COUNT`). The counters live in the cache: point
  `CACHES` at Redis or the database when there is more than one process.
- **`next` survives.** It is checked (`safe_next`), stored on the request,
  and used wherever the link is opened, so signing in from an invite, the
  MCP consent page or a deep link comes back there.
- **In development** the code page also shows the link (`DEBUG` only), and
  the email prints to the console.

## The first sign-in

An account with no name goes to `/app/welcome/` first ("what should friends
call you?"), then a one-off passkey suggestion, then the tour offer
(docs/onboarding-tour.md), and finally wherever it was going. A passkey
sign-in takes the same route.

## Passkeys

- Added from `/app/account/`, removed there too. Each is named after the
  device it was made on ("Passkey on iPhone").
- Discoverable credentials with user verification required: a passkey alone
  signs someone in, so it has to be the person, not just the device.
- Sign-in needs no email: pressing "Sign in with a passkey" makes the
  browser offer every passkey it holds for the site. Nothing asks before
  the button is pressed: no autofill (conditional mediation) request on
  page load, which some browsers and password managers show as a prompt
  nobody asked for.
- A passkey deleted here but still on a device answers 404 with its id;
  the page asks the browser to forget it (`signalUnknownCredential`).
- `WEBAUTHN_RP_ID` is the site's host name and `WEBAUTHN_ORIGINS` its
  origin(s), both from `SITE_URL` by default. A passkey only works on the
  host it was made for: moving to another domain means people add new ones.

## Staff and the admin

The admin's password form redirects to `/sign-in/`: staff sign in by email
or passkey like everyone else, and the admin opens for an account with
`is_staff`. Make one with `createsuperuser` (it asks for a password, which
nothing uses), or tick Staff on an existing account.

## Reviewer accounts

App directories (OpenAI's for ChatGPT, Anthropic's for Claude) review an
app by signing in to a test account, and refuse one that needs an inbox, an
SMS or any other verification step. A reviewer account is an address that
signs in with a fixed code instead:

1. In the admin, add a **Reviewer account** with an address that has no
   mailbox behind it, such as `reviewer@gondola.ultraniche.ai`. Its six-digit
   code is made when you save it.
2. Give the reviewers the address, the code, and: "Enter the email on the
   sign-in page, then type the code on the next page. No email is sent."
3. After the review, select the account and run **Give the selected
   accounts a new code**, or delete it.

- **Nothing else changes.** The reviewer uses `/sign-in/` and
  `/sign-in/code/` like anyone else. `sign_in.issue()` gives that address's
  request the fixed code, and the view sends it no email. The account
  itself is made on first sign-in, as for anyone.
- **Same limits.** Five wrong codes end a request, and an address gets five
  requests an hour, so the code can't be guessed in any useful time.
- **The code is kept as it is,** not hashed like an emailed code, so staff
  can read it in the admin. It is a shared test credential for an account
  with no one's data in it, not a person's secret.

## Email

Sent through `MAILERS["default"]`: the console in development, SMTP in
production (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`). Views only enqueue
`send_sign_in_email`; `TASKS` uses `apps.core.task_backends.ThreadBackend`,
which sends it on a thread of its own, so the page answers while the mail
relay is still talking. A failed send is logged (`django.tasks`, ERROR).
Tests run tasks inline, so mail is in the outbox before the response. Swap in
a queue-backed backend and a worker when volume needs it.

`purge_sign_in_requests --commit` deletes expired requests; it runs on each
deploy (render.yaml).

## Signing out

<<<<<<< before updating
`POST /sign-out/`. `pwa.js` deletes the service worker's cached pages and
the recorded user before the form posts, so the next person on the device
can't open the last one's pages offline. Unsent outbox rows stay on the
device and are sent only if the same user signs back in.

## Where Gondola differs from the template

- Its own `User`, keyed on email, with a display name, the evening email
  and the tour (docs/decisions/gondola-keeps-its-own-user-model.md). So
  `user_for` finds people by email, not username.
- It keeps the email address, not the template's key and masked address,
  because it sends the evening email
  (docs/decisions/gondola-keeps-email-addresses.md).
- Addresses are `/sign-in/…` and `/sign-out/`, as before, not `/signin/`.
- Links and codes last 30 minutes, not 15.
- The first sign-in goes through the welcome, passkey and tour pages.
- The email has an HTML part as well as text.
- Sign-out sends no `Clear-Site-Data`: Chrome on Android held the redirect
  while it cleared the cache, so the button looked dead.
=======
`POST /signout/`. `pwa.js` deletes the service worker's cached pages and
the recorded user before the form posts, so the next person on the device
can't open the last one's pages offline. Every signed-in page is sent
`no-store` (`apps/core/private_pages.py`), so Back can't show it from the
browser's cache; app pages also carry `Offline-Copy: allowed`, which lets the
service worker keep its own copy. Don't send `Clear-Site-Data: "cache"`: Chrome walks its whole
disk cache before following the redirect, which held sign-out for ~25 s. Unsent outbox rows stay on the device and are
sent only if the same user signs back in.
>>>>>>> after updating
