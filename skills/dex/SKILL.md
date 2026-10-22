---
name: dex
description: Read one Pokédex page (Lucky or ★100%) on the Android phone and print a storage search of the Pokémon missing from it, for another account to paste. Use when the user says /dex or asks for a search of what's missing from a Pokédex page.
model: claude-sonnet-5-5
---

# /dex: a search of what's missing from a Pokédex page

Uses the shared tapper and screen reader from /pvpc (`~/.claude/skills/pvpc`: `ui.py`, `run.py`, `home.py`).
`S=~/.claude/skills/dex`. Android only for now (CyrillJan's Pixel).

`POGO_PHONE=android caffeinate -dimsu python3 $S/dex.py lucky` (or `100` for the ★100% page)

It takes about 5 minutes and only taps to move around: it never changes anything in the game.

- `POGO_PHONE=android python3 $S/dex.py look`: what it reads on the grid on screen now. Taps nothing.

## What it prints

The dex numbers missing from the page, as one storage search with ranges: `14,22,29-33,35`. The other account pastes it into its Pokémon search. Add filters after it, e.g. `&!lucky` or `&4*`.

A search longer than 1,000 characters is split into several. The Pixel's search bar took 1,397 characters and failed at 1,497 (2026-10-21). The searches are also saved to `runs/<time>-<page>/missing-<page>.txt`.

## How it reads the page

1. From anywhere to the main menu, POKÉDEX, the page's chip at the bottom (LUCKY, ★100%; it swipes the chip row to find it), then KANTO.
2. The page is one long grid, 4 a row, #1 to #1024. A caught entry has a picture with its number at the bottom of the tile. A missing one is an empty tile with its number in the middle.
3. It scrolls a quarter screen at a time and reads every number by OCR. Each number's height decides: a missing number sits higher than a caught one. On the ★100% page each region starts under its own title (SINNOH), which shifts the rows.
4. How busy the tile is above the number (a picture or plain) backs the height up. It's never enough alone: a faint Togetic reads plainer than a pink empty tile.

## Checks before it prints

- Each screen shares a number with the one before (no rows skipped).
- A number skipped by the OCR gets a second read on a 3x screenshot.
- Its caught count equals the page's "Caught:" total.
- Every number from 1 to the last was read, except the species that are on neither page: the ones that can't be traded (Mew, Celebi, Jirachi, Deoxys, Phione to Arceus, Victini, Keldeo, Meloetta, Genesect, Zygarde to Volcanion, Magearna, Marshadow, Zeraora, Meltan, Melmetal, Zarude).

Any check that fails stops the run with no search printed. The log and a capture are in `runs/`.

Tested 2026-10-21 on CyrillJan: Lucky 640 caught, 361 missing, `<search>&lucky` found 0. ★100% 165 caught, 836 missing, `<search>&4*` found 0.
