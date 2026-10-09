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
  - gym defender (`GYM_DEFENDERS` in `ivc/ivc.py`): top 20 CP of that species
- **Always keep:** 98% or 100%. A shadow whose purified IV (`84/98`) is 98% or 100%. Armored Mewtwo (`OWN_FORM`: no search splits it from Mewtwo).
- **Weak lines:** a line is strong if any species in it (its mega or shadow form too) reaches `STRONG_AT` (90) on DialgaDex for any type. Data: `dialgadex-20261007.json`, pulled with `~/claude-plans/_scripts/dialgadex-scrape.mjs`. A weak line's final gets 1 spot (ties keep). The lucky and Dynamax rules still apply (`WEAK_EXTRAS`), and a name with an Elite TM move (`*`) keeps. Never weak: gym defender lines, legendary/mythical/Ultra Beast lines, lines with a mega DialgaDex doesn't rate yet, and species missing from DialgaDex. `meta-overrides.txt` marks lines by hand.
- **Vivillon patterns** (`COLLECT`): a NOPE in the Scatterbug line becomes LEAVE so the user picks.
- **Keep** = favorite (star) + untick IVC. **Fail** = untick IVC + tick Nope. If it also has PvpC, only IVC gets unticked (no Nope): /pvpc decides.
- A fail with XXL/xxs in the name is left alone for the user. A name with no IV and no size (`FP*`) gets Nope.
- **98%/100% never get Nope**, whatever the name says. `act` and the fallen-out step appraise each one before tagging Nope. A 98%+ one (a shadow: once purified) is kept instead.
- **Fallen out:** older Pokémon with an /ivc name and no IVC tag that now fall outside the top (`fallen.json`, listed at the end of plan.txt). Shiny and costume ones are never touched. Not traded + caught 2016–2020 → tag GuaranteedLucky. Not traded + older than 300 days → tag Old. Anything else (traded, since a Pokémon trades only once, or newer) → star off + Nope. Each one is judged again on its detail screen before anything changes. Steps: `run.py fallen <dir>` (read-only, sorts them into groups), then `run.py act-fallen <dir>` after `act`.
- It never renames or transfers.

## Running it

Four steps. Only the last one changes anything.

1. `caffeinate -dimsu python3 $S/run.py scan` opens every IVC Pokémon and writes `runs/<time>/scan.json`.
2. `caffeinate -dimsu python3 $S/run.py pools $S/runs/<time>` types the pool searches and writes `pools.json`. You can rerun it to carry on.
3. `python3 $S/run.py plan $S/runs/<time>` writes `plan.txt`.
4. `caffeinate -dimsu python3 $S/run.py act $S/runs/<time>` lists the NOPEs and asks `Go ahead? [y/N]` in the terminal, then favorites and untags, or Nopes. It asks once per plan. Without a terminal it stops and prints the NOPE list instead. Show that list to the user. Rerun with `--yes` only after the user says yes.

To test one search, run `python3 $S/run.py search "4&!#Nope&shadow"`.

**Android phone:** put `POGO_PHONE=android` in front of the command. See the **Android phone** section of the /pvpc skill.

## How reading works

- To clear the search bar, it closes the Pokémon screen and reopens it. A fresh screen always has an empty bar.
- After each search it reads the game's count `Q (n)` and saves it in `counts.json`.
- If the tiles it read don't match that count, `plan` tries the worst case. If the worst case flips KEEP/NOPE, the verdict becomes LEAVE.
- A search that shows no tiles and no count isn't saved. That Pokémon is SKIP until `pools` is run again.
- Tile names get cleaned before matching. The tag icon reads as `9`, `$` or `•` (`993 H` is `93 H`). `13h` and `13 h` are the same name.
- Species guesses on the same line (Tentacool or Tentacruel) sort the same, so it picks one. Gym defenders must be exact.
