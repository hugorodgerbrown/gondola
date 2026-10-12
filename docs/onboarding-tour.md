# Onboarding tour

The script for the first-run tour, locked on 12 October 2026, and built
in `apps/tour` (see "How it's built" at the end). The illustrated version,
with every frame drawn on the real screens, is the
[Gondola first-run tour](https://claude.ai/artifact/1941AZS9N4GK6gGXjbGiaF).

## Decisions

| Question | Decision |
|---|---|
| What kind of tour | Spotlights on the real screens, inside a demo group |
| Can the demo save anything | No. Look and tap only: Save moves the tour on and writes nothing |
| Who sees it | New accounts only, offered once after the name and passkey screens |
| Organisers | The same demo; the hand-off sends them to Groups to start one |
| Take it again | Yes, from the account page |
| Measure | fivebar goals (see below) |

## How the demo works

- **A copy per person.** Starting the tour creates a "Thursday crew" group
  for that person alone, with the made-up friends and their days set around
  today. Nobody touring sees anyone else.
- **Nothing is saved.** Plan days belong to a person, not a group, so a
  day saved in the demo would show in their real groups too. Save is
  intercepted.
- **Always clearly a demo.** An amber "Demo · nothing is saved · End tour"
  bar sits just above the tab bar on every tour screen. While someone
  tours, their demo copy is the only group every screen shows, the map and
  the board included, so the tour is full. Outside the tour, demo groups
  never show anywhere: not on the map, the board, the calendar or in the
  evening email.
- **Cleaned up.** Finishing or ending the tour deletes the copy. Someone who
  closes the tab has theirs deleted on their next page load, since the app
  runs no scheduled jobs.
- **One script for everyone.** The demo is always busy, so only the
  hand-off in chapter 6 depends on the person's real groups, read across
  all of them: **busy** when anyone else in any of them has said something
  about a day from today on, **quiet** when they're in a group but nobody
  else has yet, and **none** when they're in no group. A quiet group adds a
  Tell the group button that shares the invite link of their first group
  by name.

## The pattern

Each chapter opens with a page intro (a card over the dimmed page), then
zooms into one element at a time (Next moves on), and ends with a real tap
on the control that leads to the next page.

## Chapter 0: Welcome

**Page intro:** Welcome to Gondola! Gondola helps you and your friends see who's skiing where this winter, so meeting up is easy. Let's take a quick look round a demo group.

*Why:* Warm, short, and clear that this is a demo. The person has just signed in for the first time, so the first words are a greeting, not an instruction.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 0 | Welcome | Show me round | Welcome to Gondola! Gondola helps you and your friends see who's skiing where this winter, so meeting up is easy. Let's take a quick look round a demo group: it's made up, so tap anything. Nothing is saved. |

## Chapter 1: Your calendar

**Page intro:** This is your calendar. Blue days are the days you're in a resort, and the people mark shows friends will be there too.

*Why:* The calendar is where people spend most of their time, and every mark on it carries meaning. The intro names the marks; each zoom explains one control. Press and hold has no hint on the page, so the tour is where people learn it.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 1.0 | Page intro | Next | This is your calendar. Blue days are the days you're in a resort, and the people mark shows friends will be there too. |
| 1.1 | Resort chips | Next | Tap a resort to light up the days your friends will be there. |
| 1.2 | Several days | Next | Tap and hold a day to start selecting, then tap more days. Plan sets them all at once. |
| 1.3 | Day panel | Next | Tap a day to see it here: your plans, and where each friend will be. |
| 1.4 | Add plans | Tap Add plans | Add plans tells your groups where you'll be. |

## Chapter 2: A single day

**Page intro:** Planning a day. Here you tell your groups where you'll be. We show you where your friends are going first.

*Why:* The day sheet has the most going on, so it gets an overview before the details: friends first, then search, then Save.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 2.0 | Page intro | Next | Planning a day. Here you tell your groups where you'll be. We show you where your friends are going first. |
| 2.1 | Friends' resorts | Next | We show you where friends will be that day. Tap one to join them. |
| 2.2 | Search | Next | Somewhere else? Look up any resort. |
| 2.3 | Save | Tap Save | Save shares the day with your groups. |

## Chapter 3: Your group

**Page intro:** This is your group. Everyone in it sees each other's names and days. Invite friends here, and see the whole group's week in Who's where.

*Why:* Joining is consent, so the group page says plainly who sees what. It is also where the invite link lives, which is how a real group grows.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 3.0 | Page intro | Next | This is your group. Everyone in it sees each other's names and days. Invite friends here, and see the whole group's week in Who's where. |
| 3.1 | Invite link | Next | Share this link in your group chat. Friends join with one tap. |
| 3.2 | Members | Next | Everyone who's joined. They see your days, and you see theirs. |
| 3.3 | Who's where | Tap Who's where | Tap Who's where to see the group's week. |

## Chapter 4: Who's where

**Page intro:** The group's week at a glance. Everyone side by side, so you can see who overlaps where.

*Why:* The payoff of everyone planning. A full demo board teaches the codes by example, which an empty real board never could.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 4.0 | Page intro | Next | The group's week at a glance. Everyone side by side, so you can see who overlaps where. |
| 4.1 | Resort codes | Next | Each code is a resort: VERB is Verbier. Blank hasn't said. |
| 4.2 | Map tab | Tap Map | Tap Map to see where your friends are on any day. |

## Chapter 5: The map

**Page intro:** The map shows where your friends are skiing, on any day you pick. It's where you'll land each time you open Gondola.

*Why:* Sign-in lands on the map, so the numbers on pins need explaining once, while there are demo numbers to explain.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 5.0 | Page intro | Next | The map shows where your friends are skiing. On any day you pick. It's where you'll land each time you open Gondola. |
| 5.1 | Day | Next | Change the day with the arrows, or tap the date for a calendar. |
| 5.2 | Friends | Next | The number on a resort is how many friends are there that day. |
| 5.3 | Pass | Next | Show only the resorts on your pass. |
| 5.4 | Open a resort | Tap Verbier | Tap a resort to see who's there. |
| 5.5 | Resort sheet | Next | Say you'll be here without leaving the map. |

## Chapter 6: Over to you

**Page intro:** That's the tour. The demo group is gone. This is your real calendar: tap a day you might ski, then Add plans, and your group will see it.

*Why:* The amber bar disappears, so the switch from practice to real is visible, and they land where the measured goal happens. In a quiet group the card adds Tell the group; an organiser with no group lands on Groups to start one. Someone who signed up through an invite link is offered the tour only after tapping Join, so they arrive here already in the group; if they started it with the invite still pending, Let's go goes back to that invite, which comes before Groups.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 6.0 | Hand-off | Let's go | That's the tour. The demo group is gone. This is your real calendar: tap a day you might ski, then Add plans, and your group will see it. The evening before you ski, we'll email you who's where. |

## Measuring it: fivebar goals

Every event is a goal in fivebar with no setup. None carries anything about
the person. The tag is on every page under SITE_URL's domain,
gondola.ultraniche.ai (`apps/core/analytics.py`); `FIVEBAR_DOMAIN` overrides
it. Add that site in fivebar for the counts to show.

| Event | Sent when | Data |
|---|---|---|
| `Tour offered` | The welcome (chapter 0) is shown | none |
| `Tour skipped` | Not now is tapped | none |
| `Tour started` | Show me round is tapped | `replay`: true / false |
| `Tour ended` | End tour is tapped | `chapter`: 1 to 5 |
| `Tour finished` | Chapter 6 is reached | `group`: busy / quiet / none |
| `Day planned` | A real day is saved | `first`, `after_tour`: true / false |
| `Invite shared` | The invite link is shared | `from`: tour / group |

The number to watch is first days planned after the tour against those
planned without it. `Tour offered` counts everyone who saw the welcome,
and splits into `Tour skipped` and `Tour started`, so both groups have a
denominator. Toured: `Day planned` with `first` and `after_tour` true, over
`Tour finished`. Skipped: `Day planned` with `first` true and `after_tour`
false, over `Tour skipped`; accounts made before the tour shipped had
their first day before it, so they don't count in either.

## Left out on purpose

Passkeys (asked just before the tour), reset link, leave and delete.

## How it's built

- **`apps/tour/script.py`** is this script as data: every coach mark, what
  it spotlights and what it waits for. `tests/tour/test_script.py` fails if
  it drifts from the tables above.
- **`apps/tour/demo.py`** makes the copy: "Thursday crew", owned by the
  person, with six made-up friends (inactive `@tour.invalid` accounts that
  can't sign in or get email) and their week from today. The friends are
  shared by every copy; each copy is the person and them, nobody else.
- **`apps/tour/middleware.py`** reads the tour from the session. While
  touring, `Group.objects.for_user` returns the demo copy and nothing else,
  so every screen (map, calendar, board, sheets) shows the demo with no
  change of its own. Outside the tour it never returns a demo group, which
  keeps them off the evening email too. Any form posted to the planning
  screens is answered by the middleware, not its view: Save goes to the
  group, anything else stays put and says nothing was
  saved. A copy older than an hour, or one left by a closed tab, is deleted
  on the next page load.
- **`static/js/tour.js`** plays the frames over the real page: four shades
  round a hole, so only the spotlit control can be tapped. Inside a sheet
  the layer moves into the dialog, which sits above the page.
- **Offered** after the passkey screen for a new account, or after joining
  for someone who signed up through an invite link; again from the account
  page. Chapter 0 is `/tour/`.
- A frame whose target isn't on screen is skipped.
