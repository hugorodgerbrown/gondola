# Onboarding tour

The script for the first-run tour, locked on 12 October 2026, and built
in `apps/tour` (see "How it's built" at the end). The illustrated version,
with every frame drawn on the real screens, is the
[Gondola first-run tour](https://claude.ai/artifact/1941AZS9N4GK6gGXjbGiaF).

## Decisions

| Question | Decision |
|---|---|
| What kind of tour | Spotlights on the real screens, inside a demo group |
| Can the demo save anything | No. Look and tap only: Save and Propose move the tour on and write nothing |
| Who sees it | New accounts only, offered once after the name and passkey screens |
| Organisers | The same demo; the hand-off sends them to Groups to start one |
| Take it again | Yes, from the account page |
| Measure | fivebar goals (see below) |

## How the demo works

- **A copy per person.** Starting the tour creates a "Thursday crew" group
  for that person alone, with the made-up friends and their days set around
  today. Nobody touring sees anyone else.
- **Nothing is saved.** Plan days belong to a person, not a group, so a
  day saved in the demo would show in their real groups too. Save and
  Propose are intercepted.
- **Always clearly a demo.** An amber "Demo · nothing is saved · End tour"
  bar sits just above the tab bar on every tour screen. Demo groups never
  count on the map, the board or in the evening email.
- **Cleaned up.** Finishing or ending the tour deletes the copy. Someone who
  closes the tab has theirs deleted on their next page load, since the app
  runs no scheduled jobs.
- **One script for everyone.** The demo is always busy, so only the
  hand-off in chapter 7 depends on the person's real group: a quiet group
  adds a Tell the group button that shares the invite link.

## The pattern

Each chapter opens with a page intro (a card over the dimmed page), then
zooms into one element at a time (Next moves on), and ends with a real tap
on the control that leads to the next page.

## Chapter 0: Welcome

**Page intro:** Welcome to Gondola! Gondola helps you and your friends see who's skiing where this winter, and pick a place to meet. Let's take a quick look round a demo group.

*Why:* Warm, short, and clear that this is a demo. The person has just signed in for the first time, so the first words are a greeting, not an instruction.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 0 | Welcome | Show me round | Welcome to Gondola! Gondola helps you and your friends see who's skiing where this winter, and pick a place to meet. Let's take a quick look round a demo group: it's made up, so tap anything. Nothing is saved. |

## Chapter 1: Your calendar

**Page intro:** This is your calendar. It shows the days you're skiing, and how many of your friends are skiing each day.

*Why:* My days is where people spend most of their time, and every mark on it carries meaning. The intro names the page; each zoom explains one mark.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 1.0 | Page intro | Next | This is your calendar. It shows the days you're skiing, and how many of your friends are skiing each day. |
| 1.1 | Friend count | Next | The number on a day is how many friends are skiing it. |
| 1.2 | Meet-up dot | Next | An amber dot means a meet-up is planned that day. |
| 1.3 | Resort chips | Next | Tap a resort to light up the days your friends will be there. |
| 1.4 | Your days | Next | Your own days show in blue: solid when you're skiing, dashed when you're not sure. |
| 1.5 | Several days | Next | Tap and hold a day to start selecting, then tap more days. Plan sets them all at once. |
| 1.6 | Open a day | Tap the day | Tap a day to plan it. |

## Chapter 2: A single day

**Page intro:** Planning a day. Here you tell your groups where you'll be and whether you're skiing. We show you where your friends are going first.

*Why:* The day sheet has the most going on, so it gets an overview before the details: friends first, then search, then the skiing question, then the optional extras.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 2.0 | Page intro | Next | Planning a day. Here you tell your groups where you'll be and whether you're skiing. We show you where your friends are going first. |
| 2.1 | Friends' resorts | Next | We show you where friends will be that day. Tap one to join them. |
| 2.2 | Search | Next | Somewhere else? Look up any resort. |
| 2.3 | Skiing? | Next | Tell everyone whether you're on the slopes. Not sure is fine. Not skiing means you'll be around, off the slopes. |
| 2.4 | Note | Next | Add a note for your groups, like "first lift". |
| 2.5 | Private | Next | Keep a day to yourself: friends see nothing for it. |
| 2.6 | Save | Tap Save | Save shares the day with your groups. |

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
| 4.1 | Resort codes | Next | Each code is a resort: VERB is Verbier. ? is not sure, – is not skiing, blank hasn't said. |
| 4.2 | Meet-up | Next | A black box is a meet-up. Tap it for the time and meeting point. |
| 4.3 | Propose | Tap + | Tap + to propose a meet-up that day. |

## Chapter 5: A meet-up

**Page intro:** Proposing a meet-up. Gondola suggests where to meet, based on where everyone already is. Add a time and a meeting point if you like, then share it.

*Why:* The ranked suggestion is the part nobody would guess, and the optional time and pin match the product rule that only the resort is required.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 5.0 | Page intro | Next | Proposing a meet-up. Gondola suggests where to meet, based on where everyone already is. Add a time and a meeting point if you like, then share it. |
| 5.1 | Suggestion | Next | The best fit comes first: most friends already there, fewest moves. |
| 5.2 | Another resort | Next | Prefer somewhere else? Pick any resort. |
| 5.3 | Time and pin | Tap Propose | Both optional. Tap the map to drop a meeting point. |

## Chapter 6: The map

**Page intro:** The map shows where your friends are skiing, on any day you pick. It's where you'll land each time you open Gondola.

*Why:* Sign-in lands on the map, so the numbers on pins need explaining once, while there are demo numbers to explain.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 6.0 | Page intro | Next | The map shows where your friends are skiing. On any day you pick. It's where you'll land each time you open Gondola. |
| 6.1 | Day | Next | Change the day with the arrows, or tap the date for a calendar. |
| 6.2 | Friends | Next | The number on a resort is how many friends are there that day. |
| 6.3 | Pass | Next | Show only the resorts on your pass. |
| 6.4 | Open a resort | Tap Verbier | Tap a resort to see who's there. |
| 6.5 | Resort sheet | Next | Say you'll be here, or propose a meet-up, without leaving the map. |

## Chapter 7: Over to you

**Page intro:** That's the tour. The demo group is gone. This is your real calendar: tap a day you might ski, and your group will see it.

*Why:* The amber bar disappears, so the switch from practice to real is visible, and they land where the measured goal happens. In a quiet group the card adds Tell the group; an organiser with no group lands on Groups to start one.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 7.0 | Hand-off | Let's go | That's the tour. The demo group is gone. This is your real calendar: tap a day you might ski, and your group will see it. The evening before you ski, we'll email you who's where. |

## Measuring it: fivebar goals

Every event is a goal in fivebar with no setup. None carries anything about
the person. The tag is on every page under SITE_URL's domain,
gondola.ultraniche.ai (`apps/core/analytics.py`); `FIVEBAR_DOMAIN` overrides
it. Add that site in fivebar for the counts to show.

| Event | Sent when | Data |
|---|---|---|
| `Tour started` | Show me round is tapped | `replay`: true / false |
| `Tour ended` | End tour is tapped | `chapter`: 1 to 6 |
| `Tour finished` | Chapter 7 is reached | `group`: busy / quiet / none |
| `Day planned` | A real day is saved | `first`, `after_tour`: true / false |
| `Invite shared` | The invite link is shared | `from`: tour / group |
| `Meet-up proposed` | A real meet-up is saved | `from`: board / map |

The number to watch is `Day planned` (first, after tour) over
`Tour finished`, against people who skipped the tour.

## Left out on purpose

Passkeys (asked just before the tour), notes beyond one line, reset link,
leave and delete, and the shared meet-up page, which explains itself.

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
  so every screen (map, My days, board, sheets) shows the demo with no
  change of its own. Outside the tour it never returns a demo group, which
  keeps them off the evening email too. Any form posted to the planning
  screens is answered by the middleware, not its view: Save goes to the
  group, Propose to the map, anything else stays put and says nothing was
  saved. A copy older than an hour, or one left by a closed tab, is deleted
  on the next page load.
- **`static/js/tour.js`** plays the frames over the real page: four shades
  round a hole, so only the spotlit control can be tapped. Inside a sheet
  the layer moves into the dialog, which sits above the page.
- **Offered** after the passkey screen for a new account, or after joining
  for someone who signed up through an invite link; again from the account
  page. Chapter 0 is `/tour/`.
- A frame whose target isn't on screen (the meet-up dot when the demo week
  runs into next month) is skipped.
