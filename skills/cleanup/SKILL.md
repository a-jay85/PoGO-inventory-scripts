---
name: cleanup
description: Cleanup rules for Pokémon GO run on the phone. First rule: purify every shadow tagged Nope, then transfer them in one go. After trading: tag the PvpC1/PvpC2/IV Check shortcuts, power up Clean Trades ones sitting right under an XL-transfer tier, tag Clean Trades Transfer. Use when the user says /cleanup, asks to purify and transfer their Nope shadows, or to clean up after trading.
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

## After trading: tag the shortcuts, power up for XL, tag Transfer

`POGO_PHONE=android caffeinate -dimsu python3 $S/cleantrades.py [--limit N]`
`POGO_PHONE=android caffeinate -dimsu python3 $S/cleantrades.py --look` reads levels only. It taps POWER UP to read the dialog, then CANCEL. Nothing is spent or tagged.

It works off the saved search shortcuts, always in this order:

1. **PvpC1** and **PvpC2** get the PvpC tag. **IV Check** gets IVC. A shortcut the account doesn't have is skipped (CyrillJan has no PvpC ones). This step goes first. Clean Trades only shows untagged ones (`!#`), so these drop out of it.
2. **Clean Trades** + `&countcandyxl0-359` (under 360 Candy XL). For each one:
   - Its CP and max HP give the levels it could be. If none of them is 14, 19, 22 or 30 (or the half level after), it's skipped with no taps.
   - Otherwise POWER UP is tapped. The dialog's "CP a → b" and Stardust cost narrow the level. The cost changes every 2 levels (5,000 dust = level 29–30.5). Lucky and purified discounts are allowed for.
   - If that still mixes a play with a non-play, it taps + (one more power-up) up to 4 times. Each + shows a new CP and total cost that narrow it more. It never appraises.
   - At 14, 19, 22 or 30 it sets the dialog to the 1 or 2 power-ups needed to reach 15, 20, 23 or 31, and taps POWER UP once. Those are the next XL-on-transfer tiers. The plays come from `~/claude-plans/_reports/personal/pogo/xl-transfer-roi.md`. The dialog's CP after must match the level math first. A "Do you really want to power up" box gets YES.
   - Never below 1,000,000 Stardust. Below that it stops powering up, but still tags.
   - `--limit N` stops after N power-ups. The rest weren't checked, so Clean Trades isn't tagged Transfer then.
3. **Clean Trades** gets the Transfer tag. It doesn't transfer.

Tagging a shortcut: its search + `&!#<tag>`, long press a tile, SELECT ALL, TAG (n). The n must equal the search's count, and the sheet must say "TAG n POKÉMON". The tag row is found by scrolling the sheet in small steps. Afterwards the same search must come back empty.

Adding to a shortcut's search: tap the shortcut, tap the filled bar, jump to the end, type the extra part, Return. A `count…` term eats any text after it, so the XL part always goes last.

**iPhone (HashTagAJay):** not tried yet. The cursor jump to the end of the bar, multi-select and the swipe are Android-only so far. Run `--look` first, then `--limit 1`.

