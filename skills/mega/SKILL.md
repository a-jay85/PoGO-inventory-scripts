---
name: mega
description: Mega Evolve every Pokémon tagged TODO once a day, on HashTagAJay (iPhone) and CyrillJan (Android). Mewtwo, and a High Level one 1 day from Max Level, only when it's free. Use when the user says /mega or asks to Mega Evolve the TODO Pokémon.
model: claude-sonnet-5-5
---

# /mega: Mega Evolve the TODO Pokémon

Uses the shared tapper and screen reader: the shared library (`~/PoGO-inventory-scripts/skills/shared`) and /pvpc's `run.py`. `S=~/.claude/skills/mega`.

`POGO_PHONE=android caffeinate -dimsu python3 $S/mega.py [--limit N] [--dry-run]`

Or through the front door: `POGO_PHONE=android caffeinate -dimsu python3 ~/PoGO-inventory-scripts/pogo.py mega`.

`POGO_PHONE` picks the phone, like the other skills:

- `POGO_PHONE=android`: the Android phone only.
- No `POGO_PHONE`: the iPhone only. Keep your hands off the Mac mouse while it runs.
- `POGO_PHONE=both`: both phones at once, each in its own process.

`--limit N`: at most N Mega Evolutions per phone. `--dry-run`: goes as far as the "Do you want to Mega Evolve" box, then taps NO. It still taps the phone.

## What it does

It searches `#TODO&mega&!#TODO4`. `mega` only finds species that can Mega Evolve, so a Braixen is never opened. It opens the first one and swipes through them. On each one it opens the Mega level page (tap the round Mega badge under the types) and Mega Evolves from that page's MEGA EVOLVE button.

It skips a Pokémon when:

- its tag isn't exactly `TODO` (`TODO4` is left alone);
- it's Mega Evolved right now (the badge reads `07:59 left`);
- the level page says "Daily level limit met": it was Mega Evolved today. The game shows this once a different Pokémon has been Mega Evolved since;
- it's a Mewtwo and the Mega Evolution isn't free;
- it's High Level, the page says "Mega Evolve <name> 1 more time" to Max Level, and it isn't free;
- it's an X/Y species (Charizard, Raichu) and the nickname doesn't end in ` X` or ` Y`. The nickname's letter picks the tab on the level page. A Mewtwo with no letter tries both tabs and takes whichever one is free. While it rests after one form, the other tab is greyed out;
- the level page has no MEGA EVOLVE button (Max Level).

Free means no number next to the MEGA EVOLVE button, and no `xN` cost in the "Do you want to Mega Evolve" box. If the box's cost doesn't match the page's, it taps NO.

After YES the game wants a tap on the energy crystal. If another Pokémon is Mega Evolved, a 2nd box asks "Your <name> will no longer be Mega Evolved!": the script taps YES. Done is the badge reading `HH:MM left`.

## Then mega1, free only

When the TODO ones are done, it clears the bar and searches `mega1`. It Mega Evolves any of those, whatever the tag, only when it's free. That ends the Mega Evolution it just made, so that one's rest timer starts now instead of when its 8 hours run out.

The same skips apply, minus the tag rule: Mega right now, done today, no MEGA EVOLVE button, not free. An X/Y one takes its nickname's form. With no letter, it takes whichever form is free.

`--limit N` counts each search on its own: `--limit 1` can Mega Evolve one TODO and one mega1.

Never tapped: the level page's LEVEL UP button (it spends energy to skip levels).

## Runs

Each phone writes `runs/<time>-<phone>/log.txt`. On a stop it keeps the phone's screen there.
