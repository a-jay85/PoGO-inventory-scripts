---
name: ivc
description: Name the IVC Pokémon by IV% (max-stat letters, purified IV, Elite TM moves, XXL/xxs), keep the best of each species line (favorite + untick IVC) and give the rest their final tag at the door (GIV, XLX, Transfer ...). Use when the user says /ivc (or the old /ivcsort) or asks to name or sort their IVC Pokémon.
model: claude-sonnet-5-5
---

# /ivc — name the IVC Pokémon by IV, keep the best, final-tag the rest

Drives iPhone Mirroring like /pvpc (read its **Session start** and **Safety** first).
`S=~/.claude/skills/ivc`. Sort rules live in `$S/sort.py` (`python3 $S/sort.py test` checks them). Name rules live in `$S/ivc.py` (`python3 $S/ivc.py test` checks them; see **Name rules** below).
Search terms and their bugs: `~/PoGO-inventory-scripts/skills/shared/SEARCH.md`. Read it before building a search.

## Rules

- The IV comes from the nickname. An IVC Pokémon still named after its species gets its name here, in the same open where it's judged (see Running it).
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
  - gym defender (`GYM_DEFENDERS` in `$S/ivc.py`): top 20 CP or top 20 IV of that species (Chansey and Blissey each get their own 20). An IV tie goes to the one with more of HP and Defense at 15 (the name's capitals); still tied, it keeps.
- **Always keep:** 98% or 100%. A shadow whose purified IV (`84/98`) is 98% or 100%. Armored Mewtwo (`OWN_FORM`: no search splits it from Mewtwo).
- **Weak lines:** a line is strong if any species in it (its mega or shadow form too) reaches `STRONG_AT` (90) on DialgaDex for any type. Data: `dialgadex-20261007.json`, pulled with `~/claude-plans/_scripts/dialgadex-scrape.mjs`. A weak line's final gets 1 spot (ties keep). The lucky and Dynamax rules still apply (`WEAK_EXTRAS`), and a name with an Elite TM move (`*`) keeps. A lucky one still gets the full top 5/6 non-shadow spots (the lucky rule, 2026-10-30). Never weak: gym defender lines, legendary/mythical/Ultra Beast lines, lines with a mega DialgaDex doesn't rate yet, and species missing from DialgaDex. `meta-overrides.txt` marks lines by hand.
- **Vivillon patterns** (`COLLECT`): a DOOR in the Scatterbug line becomes LEAVE so the user picks.
- **Keep** = favorite (star) + untick IVC. **Fail** = untick IVC + its final tag at the door (`../shared/door.py`: GIV, XLX, Transfer ...). Not sure: left as is, on the not-sure list. If it also has PvpC, only IVC gets unticked: /pvpc decides.
- A fail with XXL/xxs in the name is left alone for the user. A name with no IV and no size (`FP*`) goes to the door.
- **98%/100% never go**, whatever the name says. The sort and the fallen-out step appraise each one before the door. A 98%+ one (a shadow: once purified) is kept instead.
- **Fallen out:** older Pokémon with an /ivc name and no IVC tag that now fall outside the top (`fallen.json`, listed at the end of plan.txt). Shiny and costume ones are never touched. Not traded + caught 2016–2020 → tag GuaranteedLucky. Not traded + older than 300 days → tag Old. Anything else (traded, since a Pokémon trades only once, or newer) → its final tag at the door (star off, name cleared), or left as it is if the door isn't sure. Each one is judged again on its detail screen before anything changes. Steps: `run.py fallen <dir>` (read-only, sorts them into groups), then `run.py act-fallen <dir>`, on a sort run's folder (`pogo.py ivc + ivc fallen last + ivc act-fallen last`).
- It never transfers. It renames only the IVC ones still named after their species, or with a nickname that's no species.

## Running it

One command, fall-outs included: `POGO_PHONE=android caffeinate -dimsu python3 ~/PoGO-inventory-scripts/pogo.py ivc + ivc fallen last + ivc act-fallen last`. Or on its own: `caffeinate -dimsu python3 $S/run.py [--limit N] [--look]`. It doesn't ask first (2026-10-27): the 98%+ appraisal and `/cleanup`'s suspects pass catch a wrong Nope.

1. It counts `#IVC&!xxl&!xxs`. Up to 60 (`SMALL`): one search reads them all. More: it goes 50 dex numbers at a time (`#IVC&!xxl&!xxs&1-50`, ...), and each block is tagged before the next is read.
2. It reads each IVC Pokémon in the block (`scan.json`). One read before on this phone with the same name and CP isn't opened: what its detail screen showed is saved (`$S/runs/<time>/read.json`, no age limit). One still named after its species isn't opened either: the name tells the species, and three searches over just those dex numbers (`&shadow`, `&lucky`, `&dynamax`) tell which pools it needs.
3. Then one family at a time: it types that family's searches (`pools.json`), once a run. It reads again (up to 2 more times) any search whose miscount could turn a KEEP or DOOR into LEAVE. The search most of the family's IVC ones show in goes last.
4. It decides (`plan.txt`) and, on that last list still on screen, acts (`act.json`):
   - LOOK (still named after its species): opened once. It's appraised and named (Name rules), its new name goes into the pools, and it's judged right there. KEEP: favorite + untick IVC. DOOR: the door. A KEEP waits (LEAVE) while the family has another one still to look at. IV too low to show: the door, unnamed. Good for PvP: PvpC, IVC off (see Name rules).
   - KEEP: favorites + unticks IVC. DOOR: the door.
   - An IVC one in another of the family's lists (a shadow, say) gets that list typed. A tile with the same name and CP but no IVC tag is an older keeper: it's passed.
5. If a LOOK was named, it plans the family again and acts on the KEEPs that were waiting for it. Each Pokémon is still opened once.
6. **Names pass** (after a whole sort; `run.py names [--limit N] [--dry-run]` on its own). It walks what's left of `#IVC` and names what the sort can't:
   - XXL/xxs ones. The sort leaves them out, so they only get named here. They keep IVC: the user decides on them.
   - A nickname that's no species. It's opened, and the detail screen tells the species (see **Nickname** below).
   - One still named after its species that the sort couldn't look at.
   The next run ranks what it named. Done names (`87/96 A*`, `FP*`, `xxs`) and Pvp names are passed over.

A stop loses nothing: `run.py sort $S/runs/<time>` carries on, the same way it started (blocks done are in `sorted.json`, families in `families.json`). `--limit N` stops after N changes. `--look` does steps 1-3 and writes `plan.txt`, changing nothing (no named-Nope pass either). A family whose named Nopes aren't all judged isn't done: a rerun finishes them.

An IVC Pokémon still named after its species has no IV in the pools, so it could beat a KEEP. Every KEEP whose searches could show it (its name's family: a Happiny holds back the Blissey line only) becomes LEAVE until it's been looked at (step 4). A name that matches no species (the names pass names it) holds back its whole block until the next run. A DOOR stays.

`python3 $S/ivc.py name <a/d/h> [--shadow] [--lucky] [--legendary] [--gym] [--size XXL|XXS] [--move "Frenzy Plant"]` gives a name (or NOPE). `python3 $S/ivc.py elite <species_id>` lists Elite TM moves.

To test one search, run `python3 $S/run.py search "4&!#Nope&shadow"`.

**Android phone:** put `POGO_PHONE=android` in front of the command. See the **Android phone** section of the /pvpc skill.

## Name rules

- **IV%** = (atk + def + hp) / 45, rounded to a whole number.
- **Who shows the IV:** shadows, luckies, legendaries/mythicals/ultra beasts (anywhere in the family, so Cosmog counts), gym defenders (`GYM_DEFENDERS` in ivc.py: Blissey, Chansey, Snorlax, Slaking, Wobbuffet, Dondozo), and anything at 93% or more.
  - Gym defenders always show it so the sort can rank them.
  - Everything else gets only the Elite TM and size parts.
  - **PvP first:** if one of those "everything else" ones passes the /pvpc test (top 100 in L, G or U), don't rename it. Remove IVC and add PvpC. /pvpc names it later.
  - If there's nothing to show, it gets no name. It gets its final tag at the door (`../shared/door.py`: GIV, XLX, Transfer ...; not sure = left as is, on the not-sure list). If it also has PvpC, only remove IVC: /pvpc decides.
- **Purified IV:** a shadow at 84% or more shows `/` and the purified IV%. Purifying adds +2 to each IV, max 15. Not shown at 100%.
- **Stat letters** (only when the IV shows):
  - A capital for each stat at 15, in the order H, A, D. A 100% gets none.
  - If no stat is 15, the highest stat in lowercase. If two tie, both go in (`ad`). If all three tie, none.
- **Elite TM move:** its initials then `*` (Frenzy Plant = `FP*`). The list of Elite TM moves comes from PvPoke's `eliteMoves`.
  - If the initials exactly match a stat-letter combo (H, A, D, HA, HD, AD, HAD), use a bare `*` stuck to the stat letters (`87/96 A*`).
- **Size:** `XXL` or `xxs`. Only the badge over the height counts. Ignore the words TALLEST and SHORTEST, and anything the team leader says.
- **Max 12 characters.** Shorten in this order until it fits:
  1. Drop spaces, starting from the right. Keep the one after the IV.
  2. Swap the size for `^`.
  3. Swap the move initials for a bare `*`.
  4. Drop the space after the IV.

Examples: `100`, `96 A`, `89 HA FP*` (lucky), `87/96 A* XXL`, `78 A S*`, `67 d`, `89/100 a S*^`, `FP* XXL`, `xxs`.

## Nickname

A nickname hides the species. Find it from the detail screen instead:
- The candy name gives the line. A baby shows the next one's candy (Azurill: MARILL CANDY).
- The type line picks the forms in that line (Alolan Vulpix is ICE).
- CP and HP rule out the forms that can't have them at any level. A high CP rules out the early stages.
- If more than one form is left, the appraisal's CP and HP check picks between them.

## How reading works

- A family's searches that differ only in the last term are typed side by side. When the list didn't scroll, the next one taps the bar, deletes back to where they differ and types only the new end (`search.edit_tail`, about `timing: edited the end` in the log). If the bar doesn't read right, it clears and types the whole search.
- To clear the search bar, it closes the Pokémon screen and reopens it. A fresh screen always has an empty bar. A new search typed over a scrolled list starts scrolled too, so after a search that scrolled it puts the list back at the top and keeps the search. On Android it holds the slider on the right edge and pulls it to the top (about 3s). If that fails, or on the iPhone, it sorts by HP and then by Name again (about 6s). The list should be sorted by Name.
- After each search it reads the game's count `Q (n)` and saves it in `counts.json`.
- If the tiles it read don't match that count, `plan` tries the worst case. If the worst case flips KEEP/DOOR, the verdict becomes LEAVE.
- A search that shows no tiles and no count isn't saved. That Pokémon is SKIP until the sort is run again.
- Tile names get cleaned before matching. The tag icon reads as `9`, `$` or `•` (`993 H` is `93 H`). `13h` and `13 h` are the same name.
- Species guesses on the same line (Tentacool or Tentacruel) sort the same, so it picks one. Gym defenders must be exact.
