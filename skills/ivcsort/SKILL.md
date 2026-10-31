---
name: ivcsort
description: Name the IVC Pokémon by IV (as /ivc does, in the same open), keep the best of each species line (favorite + untick IVC) and give the rest their final tag at the door (GIV, XLX, Transfer ...). Use when the user says /ivcsort or asks to sort their IVC Pokémon.
model: claude-sonnet-5-5
---

# /ivcsort — keep the best IVC Pokémon, final-tag the rest

Drives iPhone Mirroring like /pvpc and /ivc (read their **Session start** and **Safety** first).
`S=~/.claude/skills/ivcsort`. Rules live in `$S/sort.py` (`python3 $S/sort.py test` checks them).
Search terms and their bugs: `~/PoGO-inventory-scripts/skills/shared/SEARCH.md`. Read it before building a search.

## Rules

- The IV comes from the nickname. An IVC Pokémon still named after its species gets its /ivc name here, in the same open where it's judged (see Running it). /ivc first isn't needed.
- Each Pokémon is compared with **everything the user owns** in its line, found with in-game searches by dex number. Nope-tagged ones don't count, and neither do species-named, Pvp-named or IV-less ones.
- **Spots:** each final evolution in the family has its own spots. Non-shadow: 6 if that final's line can mega evolve (released in GO or not, `sort.py megas`), else 5. Shadow: 5 (shadows can't mega). Lucky: 1. Dynamax/Gigantamax: 3. Spots fill best IV first. A tie with last place keeps.
- **One Pokémon, one spot:** a Pokémon that could become two finals (Eevee, Kirlia, Poliwhirl, Cubone) takes whichever spot has room, so it never counts twice. Spare top males fill Gardevoir spots once Gallade's are full.
- **Gender** (`GENDER` in `sort.py`): only males become Gallade and Mothim; only females become Froslass, Vespiquen, Salazzle and Wormadam. Meowstic, Oinkologne, Basculegion and Indeedee split by gender too. Those searches add `&male` / `&female`. A male Combee or Salandit can't evolve, so it gets no spot (Nope unless 98%+).
- **Lines:** regional forms are their own line. `sort.py lines <species>` shows a family's spots and searches.
- **Keep if any of these pass:**
  - shadow: a shadow spot
  - not shadow: a non-shadow spot (normal, lucky, purified and Dynamax together). A purified `87/96` name counts as 96.
  - purified: a shadow with no shadow spot whose purified IV (`84/96` → 96) gets a non-shadow spot. The family's other spot-less shadows compete there too, at their purified IV.
  - lucky: a lucky spot
  - Dynamax/Gigantamax: a Dynamax spot
  - gym defender (`GYM_DEFENDERS` in `ivc/ivc.py`): top 20 CP or top 20 IV of that species (Chansey and Blissey each get their own 20). An IV tie goes to the one with more of HP and Defense at 15 (the name's capitals); still tied, it keeps.
- **Always keep:** 98% or 100%. A shadow whose purified IV (`84/98`) is 98% or 100%. Armored Mewtwo (`OWN_FORM`: no search splits it from Mewtwo).
- **Weak lines:** a line is strong if any species in it (its mega or shadow form too) reaches `STRONG_AT` (90) on DialgaDex for any type. Data: `dialgadex-20261007.json`, pulled with `~/claude-plans/_scripts/dialgadex-scrape.mjs`. A weak line's final gets 1 spot (ties keep). The lucky and Dynamax rules still apply (`WEAK_EXTRAS`), and a name with an Elite TM move (`*`) keeps. A lucky one still gets the full top 5/6 non-shadow spots (the lucky rule, 2026-10-30). Never weak: gym defender lines, legendary/mythical/Ultra Beast lines, lines with a mega DialgaDex doesn't rate yet, and species missing from DialgaDex. `meta-overrides.txt` marks lines by hand.
- **Vivillon patterns** (`COLLECT`): a DOOR in the Scatterbug line becomes LEAVE so the user picks.
- **Keep** = favorite (star) + untick IVC. **Fail** = untick IVC + its final tag at the door (`../shared/door.py`: GIV, XLX, Transfer ...). Not sure: left as is, on the not-sure list. If it also has PvpC, only IVC gets unticked: /pvpc decides.
- A fail with XXL/xxs in the name is left alone for the user. A name with no IV and no size (`FP*`) goes to the door.
- **98%/100% never go**, whatever the name says. The sort and the fallen-out step appraise each one before the door. A 98%+ one (a shadow: once purified) is kept instead.
- **Fallen out:** older Pokémon with an /ivc name and no IVC tag that now fall outside the top (`fallen.json`, listed at the end of plan.txt). Shiny and costume ones are never touched. Not traded + caught 2016–2020 → tag GuaranteedLucky. Not traded + older than 300 days → tag Old. Anything else (traded, since a Pokémon trades only once, or newer) → its final tag at the door (star off, name cleared), or left as it is if the door isn't sure. Each one is judged again on its detail screen before anything changes. Steps: `run.py fallen <dir>` (read-only, sorts them into groups), then `run.py act-fallen <dir>`, on a sort run's folder (`pogo.py ivcsort + ivcsort fallen last + ivcsort act-fallen last`).
- It never transfers. It renames only the IVC ones still named after their species (the /ivc name).

## Running it

One command, fall-outs included: `POGO_PHONE=android caffeinate -dimsu python3 ~/PoGO-inventory-scripts/pogo.py ivcsort + ivcsort fallen last + ivcsort act-fallen last`. Or on its own: `caffeinate -dimsu python3 $S/run.py [--limit N] [--look]`. It doesn't ask first (2026-10-27): the 98%+ appraisal and `/cleanup`'s suspects pass catch a wrong Nope.

1. It counts `#IVC&!xxl&!xxs`. Up to 60 (`SMALL`): one search reads them all. More: it goes 50 dex numbers at a time (`#IVC&!xxl&!xxs&1-50`, ...), and each block is tagged before the next is read.
2. It reads each IVC Pokémon in the block (`scan.json`). One read before on this phone with the same name and CP isn't opened: what its detail screen showed is saved (`ivc/runs/<time>/read.json` and `ivcsort/runs/<time>/read.json`, no age limit). One still named after its species isn't opened either: the name tells the species, and three searches over just those dex numbers (`&shadow`, `&lucky`, `&dynamax`) tell which pools it needs.
3. Then one family at a time: it types that family's searches (`pools.json`), once a run. It reads again (up to 2 more times) any search whose miscount could turn a KEEP or DOOR into LEAVE. The search most of the family's IVC ones show in goes last.
4. It decides (`plan.txt`) and, on that last list still on screen, acts (`act.json`):
   - LOOK (still named after its species): opened once. It's appraised and named as /ivc does, its new name goes into the pools, and it's judged right there. KEEP: favorite + untick IVC. DOOR: the door. A KEEP waits (LEAVE) while the family has another one still to look at. IV too low to show: the door, unnamed. Good for PvP: PvpC, as /ivc does.
   - KEEP: favorites + unticks IVC. DOOR: the door.
   - An IVC one in another of the family's lists (a shadow, say) gets that list typed. A tile with the same name and CP but no IVC tag is an older keeper: it's passed.
5. If a LOOK was named, it plans the family again and acts on the KEEPs that were waiting for it. Each Pokémon is still opened once.

A stop loses nothing: `run.py sort $S/runs/<time>` carries on, the same way it started (blocks done are in `sorted.json`, families in `families.json`). `--limit N` stops after N changes. `--look` does steps 1-3 and writes `plan.txt`, changing nothing (no named-Nope pass either). A family whose named Nopes aren't all judged isn't done: a rerun finishes them.

An IVC Pokémon still named after its species has no IV in the pools, so it could beat a KEEP. Every KEEP whose searches could show it (its name's family: a Happiny holds back the Blissey line only) becomes LEAVE until it's been looked at (step 4). A name that matches no species (only /ivc can name that one) holds back its whole block. A DOOR stays.

To test one search, run `python3 $S/run.py search "4&!#Nope&shadow"`.

**Android phone:** put `POGO_PHONE=android` in front of the command. See the **Android phone** section of the /pvpc skill.

## How reading works

- A family's searches that differ only in the last term are typed side by side. When the list didn't scroll, the next one taps the bar, deletes back to where they differ and types only the new end (`search.edit_tail`, about `timing: edited the end` in the log). If the bar doesn't read right, it clears and types the whole search.
- To clear the search bar, it closes the Pokémon screen and reopens it. A fresh screen always has an empty bar. A new search typed over a scrolled list starts scrolled too, so after a search that scrolled it puts the list back at the top and keeps the search. On Android it holds the slider on the right edge and pulls it to the top (about 3s). If that fails, or on the iPhone, it sorts by HP and then by Name again (about 6s). The list should be sorted by Name.
- After each search it reads the game's count `Q (n)` and saves it in `counts.json`.
- If the tiles it read don't match that count, `plan` tries the worst case. If the worst case flips KEEP/DOOR, the verdict becomes LEAVE.
- A search that shows no tiles and no count isn't saved. That Pokémon is SKIP until the sort is run again.
- Tile names get cleaned before matching. The tag icon reads as `9`, `$` or `•` (`993 H` is `93 H`). `13h` and `13 h` are the same name.
- Species guesses on the same line (Tentacool or Tentacruel) sort the same, so it picks one. Gym defenders must be exact.
