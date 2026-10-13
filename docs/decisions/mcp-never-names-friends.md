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

The user's own days are still read and written in full.

## Consequences

- An assistant can answer "where's busy on Saturday?" or "how many of the
  Thursday crew are in Verbier next week?", but not "who's in Verbier?" or
  "where is Ben?". The app itself still shows names; only the connector
  doesn't.
- A count can still point at someone when the user already knows who is
  in a small group. That stays between the user and their own assistant;
  the count tells the assistant's company nothing about who that is.
- A group's name is the user's own label and is still returned. If a group
  is named after a person, that name goes too.
- A new tool that reads other people's plans must aggregate them the same
  way. Adding names back is a product decision, made in a PR that says so.
