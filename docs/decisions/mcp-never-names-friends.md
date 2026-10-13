# The MCP tools never name a friend

Status: proposed (2026-10-13)

## Context

The MCP endpoint lets a person connect an assistant such as Claude, which
then reads Gondola as them. Until now `whos_where`, `where_is` and
`my_groups` answered with the names and days of everyone in their groups.
Whatever a tool returns leaves Gondola for the company that runs the
assistant. Joining a group is consent to share your name and days with the
group, not with a third party that one member chose.

## Decision

About other people, a tool answers only with counts:

- `whos_where`: for each day and resort, how many friends will be there
  (`friends`), and whether the user will (`you`).
- `my_groups`: each group's name, how many members it has, and whether the
  user owns it (`yours`).
- `where_is` ("where is Ben?") is removed: it can't be answered without
  naming someone.

The user's own days are still read and written in full. Every day in
`whos_where`, and every group in `my_groups`, carries a `see_who` link into
the app (the Calendar on that day, or the group's page), and the tool
descriptions and server instructions tell the assistant to pass it on, so
"who?" is one tap away, behind the user's own sign-in. Each such answer
also says, in a `privacy` field, that names are withheld for privacy, and
the instructions ask the assistant to tell the user so, so a missing name
reads as a choice rather than a fault.

## Consequences

- An assistant can answer "where's busy on Saturday?" or "how many of the
  Thursday crew are in Verbier next week?", but not "who's in Verbier?" or
  "where is Ben?" itself. It hands over the link instead; whether it shows
  that link is up to the assistant, which the descriptions only ask.
- A count can still point at someone when the user already knows who is
  in a small group. That stays between the user and their own assistant;
  the count tells the assistant's company nothing about who that is.
- A group's name is the user's own label and is still returned. If a group
  is named after a person, that name goes too.
- A new tool that reads other people's plans must aggregate them the same
  way. Adding names back is a product decision, made in a PR that says so.
