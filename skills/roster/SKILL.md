---
name: roster
description: HashTagAJay's best 6 raid attackers against every raid boss, from DialgaDex's counter lists and a count of the good copies in storage, and which species a new traded copy would still help with. Use when the user says /roster or asks which raid attackers they're missing.
model: claude-sonnet-5-5
---

# /roster: the top 6 against every raid boss

Uses the shared tapper and screen reader from /pvpc and /dex (`~/.claude/skills/pvpc`, `~/.claude/skills/dex`).
`S=~/.claude/skills/roster`. Android only for now, with HashTagAJay signed in on the Pixel.

1. `node $S/pull.mjs`: DialgaDex's counters for every boss, into `dialgadex-counters-<date>.json` (about 2 minutes, the Mac only). Needs Playwright (loaded from the IBL5 checkout, `PLAYWRIGHT=` to point elsewhere).
2. `POGO_PHONE=android caffeinate -dimsu python3 $S/roster.py count`: counts the good copies by search. It only searches and reads: it never changes anything in the game. It stops if the signed-in trainer isn't HashTagAJay. A stopped run goes on from where it was: `roster.py count runs/<time>-count/counts.json`.
3. `python3 $S/roster.py report [counts.json]`: the top 6s and the trade lists again, the Mac only.

Output in `runs/<time>-count/`: `counts.json`, `roster.json` (read by /cleanup's `tradeable.py`) and `report.md`.

## The rules

- DialgaDex's own filters: best moves with Elite TMs, Off Types off, only released attackers. Bosses: every entry, unreleased too. Cosmetic forms with the same types, stats and moves are pulled once.
- A good copy is 3★ or 4★. Shadows are counted apart.
- An earlier stage counts as its evolution: a 4★ Gastly is a Gengar. In a branched family, each unevolved copy counts for one branch only, the one on the most boss lists.
- One mega (or primal) per team, and only with a copy of its base species.
- Forms of one species (Mewtwo and Armored Mewtwo, Apex Lugia) are told apart by a move only one form can know (`@move`). What's left goes to the weakest form, and the report lists it as counted by a guess.
- A new traded copy (never shadow) of a species helps against a boss if it would get into its 6. #1 somewhere is Reroll, #2-#6 is GIV. Legendary, Mythical and Ultra Beast species are never on these lists: they're traded by hand.

## Checking it

`report.md` starts with the teams for Groudon, Kyogre, Rayquaza, Mewtwo and Dialga. Look at those against what you know you have before trusting the trade lists.
