---
name: cleanup
description: Cleanup rules for Pokémon GO run on the phone. First rule: purify every shadow tagged Nope, then transfer them in one go. Use when the user says /cleanup or asks to purify and transfer their Nope shadows.
model: claude-sonnet-5-5
---

# /cleanup — cleanup rules

Uses the shared tapper and screen reader from /pvpc (`~/.claude/skills/pvpc`: `ui.py`, `run.py`, `search.py`).
`S=~/.claude/skills/cleanup`.
Search terms and their bugs: `~/.claude/skills/pvpc/SEARCH.md`. Read it before building a search.

## Shadows in Nope: purify, then transfer

`caffeinate -dimsu python3 $S/shadows.py [--limit N]`

1. Checks that `#Nope&purified` is empty. If it isn't, it stops. Otherwise the bulk transfer could take older purified ones.
2. Searches `#Nope&shadow&!shiny&!costume`. The bar has to read back exactly, because one lost `!` would flip the filter.
3. Opens the first one. It purifies it only if all of these hold:
   - its only tag is Nope
   - no star
   - no XXL/XXS in the name
   - not legendary, mythical or an Ultra Beast (checked by its candy)
   - enough candy and Stardust
   - its appraisal reads under 98% once purified (a wrong name can land a 98% one in Nope). Trade retagging checks this too.
   Anything else is passed over, and it swipes to the next one.
4. Purify: one PURIFY tap, then a check that the dialog names this Pokémon, then one YES tap. It waits until PURIFY is gone, POWER UP is back and the CP has changed (about 13s of animation). It never taps twice: POWER UP moves into PURIFY's spot.
5. After a purify, the swipe stops working, because it no longer fits the search. So it goes back to the list and opens the top tile again.
6. At the end it searches `#Nope&purified`, long-presses a tile, then taps SELECT ALL. It transfers only if `TRANSFER (n)` and the dialog's "transfer n" both equal the number this run purified. If not, it leaves multi-select and stops.

`--limit N` purifies at most N, then transfers those.
If a run stops after purifying, run `python3 $S/shadows.py transfer $S/runs/<time>` to transfer what it purified (`purified.json`).
Each run writes `runs/<time>/log.txt` with timings for every step.

**Android phone:** put `POGO_PHONE=android` in front. See the **Android phone** section of the /pvpc skill.
**iPhone:** same code path (taps go through the Mac helper). Multi-select (long press, SELECT ALL, TRANSFER (n)) and the swipe haven't been tried on the iPhone yet. Run `--limit 1` first and watch.

## Timing (Pixel, 2026-10-08)

About 20–25s per Pokémon: ~13s is the game's purify animation, ~2s to the dialog, ~4–7s back to the list and into the next one. The bulk transfer takes ~2s for the lot.
