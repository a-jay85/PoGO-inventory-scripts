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

### Lucky: holes you can fill yourself

On the Lucky page it then searches this account's storage for lucky Pokémon that could evolve into a missing one, e.g. a lucky Shellder for a missing Cloyster. Those numbers are left out of the search and printed as a to-evolve list (also in `runs/<time>-lucky/evolve-lucky.txt`). The page as read is in `page-lucky.txt`.

- A whole family goes, or none of it. Applin needs 3 lucky copies to fill Flapple, Appletun and Dipplin/Hydrapple. With 2, all four stay in the search and the list says so.
- It searches `lucky&<dex>&!costume`: many costumed Pokémon can't evolve. Regional forms count only for their own evolutions (Galarian Farfetch'd for Sirfetch'd).
- Only the right gender counts for Vespiquen, Froslass, Salazzle, Mothim, Wormadam and Gallade.
- Never left out: Escavalier and Accelgor (a lucky can't be traded again), Dustox from Wurmple (random) and Basculegion (a search can't pick out White-Striped Basculin). The last two are listed as "check by hand".
- An evolution GO doesn't have yet (Duraludon to Archaludon, 2026-10) still counts: it will come.
- The list ends with a search for those lucky Pokémon (`lucky&!costume&90,238,...`), to tag them so a cleanup doesn't transfer them before they're evolved. It has every lucky that could help fill a hole still open, maybes too (Wurmple, Basculin, 2 Applin for 3 branches). It also finds a few of the wrong form or gender (a Kanto Farfetch'd, a male Combee).
- Gimmighoul and Gholdengo are left out of the search: they show on the page but can't be traded.
- `POGO_PHONE=android caffeinate -dimsu python3 $S/dex.py evolve [run folder]` does this step again on a page already read (default: the newest Lucky run). Be on the same account.

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
- Every number from 1 to the last was read, except the species that may be missing from a page: the ones that can't be traded (Mew, Celebi, Jirachi, Deoxys, Phione to Arceus, Victini, Keldeo, Meloetta, Genesect, Zygarde to Volcanion, Magearna, Marshadow, Zeraora, Meltan, Melmetal, Zarude). Some still show on some accounts (HashTagAJay: Meltan on Lucky, Darkrai and Genesect on ★100%). Those are read like any other number.

Any check that fails stops the run with no search printed. The log and a capture are in `runs/`.

Tested 2026-10-21 on CyrillJan: Lucky 640 caught, 361 missing, `<search>&lucky` found 0. ★100% 165 caught, 836 missing, `<search>&4*` found 0.

Tested 2026-10-21 on HashTagAJay: Lucky 853 caught, 149 missing, `<search>&lucky` found 0. ★100% 401 caught, 602 missing in 2 searches, each `<search>&4*` found 0. The 3x re-read fired once on each page and filled the gap.
