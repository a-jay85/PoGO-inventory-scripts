---
name: backlog
description: "The phone backlog: things to check, verify or fix on a phone that can't be done now live as GitHub Issues in the private repo a-jay85/PoGO-inventory-scripts-backlog. Use when a run leaves something that needs a look on a phone, when filing, searching or closing one, and when both phones are free to work it (/backlog)."
last_verified: 2026-11-22
---

# Phone backlog

Issues live in the private repo `a-jay85/PoGO-inventory-scripts-backlog`. This repo is public, and an issue names
trainers, species, CPs and IVs, so none of it goes in this repo's Issues or in a markdown file here.
`backlog.py` (repo root) is the one way in. Its top comment has every command.

## File one

File when something needs a phone but can't be done now: the phone is busy, the user is using it, or a run left a
Pokémon unsure (a read that failed, a by-hand call, a list that ended early).

1. Search first: `python3 backlog.py search "<species or reader>"`. One that's open gets a comment
   (`backlog.py comment <n> "<the new run, what it saw>"`), not a new issue.
2. File: `python3 backlog.py new <phone> <kind> "<title>" "<body>"`.
   - phone: `pixel`, `iphone` or `both`. kind: `verify`, `fix` or `by-hand`.
   - The body's first line is where it came from: the run folder (`skills/cleanup/runs/<stamp>-again-giv`), a
     `/tmp/pogo-watch/<stamp>.log`, or a PR URL of this repo. It cites a `file:line` and says what to look at and what
     goes wrong if nobody does. `new` exits 2 and names the rule it broke otherwise.
   - Title: the Pokémon or the script step, e.g. `Rattata CP457 2/3/2 (HashTagAJay #GIV): size not read`.
3. Many of one kind from one run (50 species specieswise wasn't sure of): one issue with a checklist.

## Work it

When both phones are free, or the user says to:

1. `python3 backlog.py ready`. Exit 1 means a phone is busy or out of reach: say which, and stop.
2. For each open issue, oldest first, read it and do what it says. Everything goes through the usual rules (CLAUDE.md):
   - verify: look with `peek.py` or the script's own read, then close with what was seen:
     `backlog.py close <n> "<what the phone showed, the run folder>"`.
   - fix: worktree, fix, tests, a `watch.py` phone run, PR, merge, pull. Close with the PR URL.
   - by-hand: the user's call. Read the facts off the phone, put them in a comment, and leave it open for the user.
     Never tag one.
3. Something that can't be settled now gets a comment saying why, and stays open.
