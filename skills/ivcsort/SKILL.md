---
name: ivcsort
description: After /ivc has renamed the IVC Pokémon, keep the best of each species line (favorite + untick IVC) and swap the rest to Nope. Use when the user says /ivcsort or asks to sort their IVC Pokémon.
model: claude-sonnet-5-5
---

# /ivcsort — keep the best IVC Pokémon, Nope the rest

Drives iPhone Mirroring like /pvpc and /ivc (read their **Session start** and **Safety** first).
`S=~/.claude/skills/ivcsort`. Rules live in `$S/sort.py` (`python3 $S/sort.py test` checks them).
Search terms and their bugs: `~/.claude/skills/pvpc/SEARCH.md`. Read it before building a search.

## Rules

- Run it after /ivc has renamed every IVC Pokémon. The IV comes from the nickname.
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
- **Weak lines:** a line is strong if any species in it (its mega or shadow form too) reaches `STRONG_AT` (90) on DialgaDex for any type. Data: `dialgadex-20261007.json`, pulled with `~/claude-plans/_scripts/dialgadex-scrape.mjs`. A weak line's final gets 1 spot (ties keep). The lucky and Dynamax rules still apply (`WEAK_EXTRAS`), and a name with an Elite TM move (`*`) keeps. Never weak: gym defender lines, legendary/mythical/Ultra Beast lines, lines with a mega DialgaDex doesn't rate yet, and species missing from DialgaDex. `meta-overrides.txt` marks lines by hand.
- **Vivillon patterns** (`COLLECT`): a NOPE in the Scatterbug line becomes LEAVE so the user picks.
- **Keep** = favorite (star) + untick IVC. **Fail** = untick IVC + tick Nope. If it also has PvpC, only IVC gets unticked (no Nope): /pvpc decides.
- Nope isn't the end: `/cleanup`'s `tradeable.py tag --nope` swaps each Nope for GIV, XLX or Transfer (see /cleanup's "Nope" section). Chain it after the sort: `pogo.py ivc + ivcsort + tradeable tag --nope`.
- A fail with XXL/xxs in the name is left alone for the user. A name with no IV and no size (`FP*`) gets Nope.
- **98%/100% never get Nope**, whatever the name says. The sort and the fallen-out step appraise each one before tagging Nope. A 98%+ one (a shadow: once purified) is kept instead.
- **Fallen out:** older Pokémon with an /ivc name and no IVC tag that now fall outside the top (`fallen.json`, listed at the end of plan.txt). Shiny and costume ones are never touched. Not traded + caught 2016–2020 → tag GuaranteedLucky. Not traded + older than 300 days → tag Old. Anything else (traded, since a Pokémon trades only once, or newer) → star off + Nope. Every one gets its name cleared too. Each one is judged again on its detail screen before anything changes. Steps: `run.py fallen <dir>` (read-only, sorts them into groups), then `run.py act-fallen <dir>`, on a sort run's folder (`pogo.py ivcsort + ivcsort fallen last + ivcsort act-fallen last`).
- It never renames or transfers.

## Running it

One command, after /ivc: `POGO_PHONE=android caffeinate -dimsu python3 ~/PoGO-inventory-scripts/pogo.py ivc + ivcsort`. Or on its own: `caffeinate -dimsu python3 $S/run.py [--limit N] [--look]`. It doesn't ask first (2026-10-27): the 98%+ appraisal and `/cleanup`'s suspects pass catch a wrong Nope.

1. It counts `#IVC&!xxl&!xxs`. Up to 60 (`SMALL`): one search reads them all. More: it goes 50 dex numbers at a time (`#IVC&!xxl&!xxs&1-50`, ...), and each block is tagged before the next is read.
2. It opens each IVC Pokémon in the block and reads it (`scan.json`). One that /ivc renamed in the last 12 hours on this phone isn't opened: /ivc saved what its detail screen showed (`ivc/runs/<time>/read.json`).
3. Then one family at a time: it types that family's searches (`pools.json`), once a run. It reads again (up to 2 more times) any search whose miscount could turn a KEEP or NOPE into LEAVE. The search most of the family's IVC ones show in goes last.
4. It decides (`plan.txt`) and, on that last list still on screen, favorites + unticks IVC, or Nopes (`act.json`). An IVC one in another of the family's lists (a shadow, say) gets that list typed. A tile with the same name and CP but no IVC tag is an older keeper: it's passed.
5. Then the family's named Nopes: untraded ones that still have an /ivc or Pvp name (/cleanup's `SUSPECT_PILE`). The first family searches the whole pile once and lists its named tiles, leaving out the Nopes this run just made (`named_nopes.json`; over 60, `NAMED_READ_MAX`, it doesn't list them). None, or every one judged already: no family searches. Else each family searches its own (`<dexes>&` + the pile), and each one there is opened, appraised and judged again, IV and PvP, with /cleanup's `suspects.py` (`nopes.json`). The Nopes this run just made are passed, and they don't count as rivals. Still belongs: star on, Nope off (a PvP keeper too: no PvpC). Fell out: name cleared, Nope stays, so `tradeable.py tag --nope` tags it next in its usual order. Unsure: left alone. One that needs a PvP line's searches gets judged after the walk, once they're typed. The first family with any reads the trainer off the profile once (`trainer.json`). Then the next family.

A stop loses nothing: `run.py sort $S/runs/<time>` carries on, the same way it started (blocks done are in `sorted.json`, families in `families.json`). `--limit N` stops after N changes. `--look` does steps 1-3 and writes `plan.txt`, changing nothing (no named-Nope pass either). A family whose named Nopes aren't all judged isn't done: a rerun finishes them.

An IVC Pokémon still named after its species has no IV in the pools, so it could beat a KEEP. Every KEEP its block could hold becomes LEAVE until /ivc renames it. A NOPE stays.

To test one search, run `python3 $S/run.py search "4&!#Nope&shadow"`.

**Android phone:** put `POGO_PHONE=android` in front of the command. See the **Android phone** section of the /pvpc skill.

## How reading works

- A family's searches that differ only in the last term are typed side by side. When the list didn't scroll, the next one taps the bar, deletes back to where they differ and types only the new end (`search.edit_tail`, about `timing: edited the end` in the log). If the bar doesn't read right, it clears and types the whole search.
- To clear the search bar, it closes the Pokémon screen and reopens it. A fresh screen always has an empty bar. A new search typed over a scrolled list starts scrolled too, so after a search that scrolled it puts the list back at the top and keeps the search. On Android it holds the slider on the right edge and pulls it to the top (about 3s). If that fails, or on the iPhone, it sorts by HP and then by Name again (about 6s). The list should be sorted by Name.
- After each search it reads the game's count `Q (n)` and saves it in `counts.json`.
- If the tiles it read don't match that count, `plan` tries the worst case. If the worst case flips KEEP/NOPE, the verdict becomes LEAVE.
- A search that shows no tiles and no count isn't saved. That Pokémon is SKIP until the sort is run again.
- Tile names get cleaned before matching. The tag icon reads as `9`, `$` or `•` (`993 H` is `93 H`). `13h` and `13 h` are the same name.
- Species guesses on the same line (Tentacool or Tentacruel) sort the same, so it picks one. Gym defenders must be exact.
