# DESIGN.md — the Titan design rules

Every Titan app has its own design system, kept in its own repository. This
file is the part they share: the rules every one of those design systems
follows. It comes from the
[django-titan-template](https://github.com/hugorodgerbrown/django-titan-template);
change it there, not here, so `copier update` keeps every app on the same
rules. `tests/test_design.py` checks each rule it can, and fails the build
when one is broken.

## 1. There is a design system, and it is in the code

An app's design system is three things, all in its repository:

- **Tokens**: the custom properties on `:root` in `static/css/app.css`.
  Every colour, font size, space, corner and shadow the app uses is one.
- **Components**: the classes below the tokens in the same file, built only
  from tokens. One stylesheet, no build step.
- **The design page** at `/app/design/` (`apps/design`, staff only): every
  token, read from the stylesheet, and every component in each of its
  states, drawn by the real CSS.

The design page is the reference. A screenshot, a mockup or this file is
not: where they disagree with the page, the page is right.

## 2. Consult it on every UI change

Before changing anything people see:

1. Open the design page and find the component that already does the job.
   Use it as it is.
2. If none does, change or add a component on the design page first, then
   use it in the screen.
3. A pull request that changes the UI shows a screenshot of the screen and,
   if a component changed, of the design page.

A one-off style in a screen (a new colour, a nudge of 3px, a class used
once) is the thing to avoid. Make it a component or a token, or do without.

## 3. Keep it in sync with the code

- The page reads its tokens from `app.css`, so they can't drift.
- Every component class, and every modifier (`--state`), is shown on the
  design page. A component that can't be (the page frame, the launch
  screen) is listed in `apps/design/conf.py` with the reason.
- The page uses only classes that exist in `app.css`.

A change that adds a component, a state or a token adds it to the page in
the same pull request.

## 4. Use tokens; hard-code nothing

Outside `:root`, `app.css` names no raw values for these:

| What | Written as | Not |
| --- | --- | --- |
| Colour | `var(--accent)` | `#2563eb`, `rgba(…)`, `white` |
| Font size | `var(--type-sm)` | `13px`, `0.8125rem` |
| Margin, padding, gap | `var(--space-md)` | `12px`, `0.75rem` |
| Corner | `var(--radius-card)` | `12px`, `50%` |
| Soft shadow | `var(--shadow-float)` | `0 1px 4px rgba(…)` |

Allowed as written: `0`, `auto`, `inherit`, `transparent`, `currentColor`,
`env(…)`, border widths, and a ring drawn as a shadow with no offset or
blur (`inset 0 0 0 2px var(--accent)`). Sizes of things (a 44px button, a
28px spinner) are not spacing and may be literal.

Also:

- **A tint is a token.** A paler or see-through colour (`--accent-soft`) is
  declared once on `:root`, not mixed in a component.
- **Icons take their colour from the text.** An inline SVG uses
  `currentColor`. An SVG in a data URI may only be a `mask-image`, painted
  with a token background.
- **Scripts and templates hold no colours.** A script that needs one reads
  the token with `getComputedStyle`. Emails are the exception: mail clients
  don't read the stylesheet, so they inline their colours.
- **Dark mode redefines tokens, never components.**

## 5. Keep the system small

| Family | Name | Limit |
| --- | --- | --- |
| Colours | any name | 20 |
| Font sizes | `--type-*` | 8 |
| Spacing | `--space-*` | the shared scale below |
| Corners | `--radius-*` | 5 |
| Soft shadows | `--shadow-*` | 4 |

Spacing is one 4px scale for every app. An app declares the steps it uses,
by these names and values, and no others:

| Token | `--space-2xs` | `--space-xs` | `--space-sm` | `--space-md` | `--space-lg` | `--space-xl` | `--space-2xl` | `--space-3xl` | `--space-4xl` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Value | 2px | 4px | 8px | 12px | 16px | 20px | 24px | 32px | 48px |

Reaching a limit means two tokens are doing one job. Merge them rather than
raising the limit; a limit changes here, for every app, or not at all.

## 6. Prune

- **No dead CSS.** Every class in `app.css` is put on an element by a
  template, a script or Python. A class built from a prefix
  (`chip--{{ kind }}`) counts for every class with that prefix. The
  design page doesn't count: it shows everything. A class a framework adds
  (Django's `errorlist`) is listed in `apps/design/conf.py`.
- **No dead tokens.** Every token is read by the CSS or a script.
- Delete a component's CSS in the same change that removes its last use.

## 7. Accessible by default

- Text tokens keep a contrast of at least 4.5:1 on the backgrounds they
  sit on (3:1 for text 24px and up).
- Anything tapped is at least 44px in its smaller dimension.
- Focus is visible on everything that takes it.
- Colour is never the only signal: a state also changes a shape, an icon
  or a word.
