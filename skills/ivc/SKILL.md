---
name: ivc
description: Appraise Pokémon GO Pokémon tagged "IVC" through iPhone Mirroring and rename them by IV% (with max-stat letters, purified IV, Elite TM moves and XXL/xxs), or swap the tag to "Nope" (or "PvpC" for low-IV PvP candidates). Use when the user says /ivc or asks to process their IVC Pokémon.
model: claude-sonnet-5-5
---

# /ivc — rename IVC Pokémon by IV%

Works like /pvpc and borrows its screen reader, tapper and helper (`~/.claude/skills/pvpc/ui.py`). Read that skill's
**Session start**, tapping rules and **Safety** section first. They all apply here.

- `S=~/.claude/skills/ivc`, `P=~/.claude/skills/pvpc`
- `python3 $S/ivc.py name <a/d/h> [--shadow] [--lucky] [--legendary] [--gym] [--size XXL|XXS] [--move "Frenzy Plant"]` gives the name (or NOPE).
- `python3 $S/ivc.py elite <species_id>` lists the species' Elite TM moves.
- `python3 $S/ivc.py test` checks the name rules against the user's examples.

## Unattended mode

`caffeinate -dimsu python3 $S/run.py [--limit N] [--dry-run]` does the whole loop with no Claude.
- `--dry-run` reads and appraises but changes nothing. It logs the name each Pokémon would get.
- It skips anything unsure and stops on anything unexpected. Logs and captures go in `$S/runs/<time>/`.
- Use this skill by hand to clear its skips.

**Android phone:** put `POGO_PHONE=android` in front of the command. See the **Android phone** section of the /pvpc skill.

## Name rules

- **IV%** = (atk + def + hp) / 45, rounded to a whole number.
- **Who shows the IV:** shadows, luckies, legendaries/mythicals/ultra beasts (anywhere in the family, so Cosmog counts), gym defenders (`GYM_DEFENDERS` in ivc.py: Blissey, Chansey, Snorlax, Slaking, Wobbuffet, Dondozo), and anything at 93% or more.
  - Gym defenders always show it so `/ivcsort` can rank them.
  - Everything else gets only the Elite TM and size parts.
  - **PvP first:** if one of those "everything else" ones passes the /pvpc test (top 100 in L, G or U), don't rename it. Remove IVC and add PvpC. /pvpc names it later.
  - If there's nothing to show, it gets no name. Remove IVC and add Nope instead. If it also has PvpC, only remove IVC (no Nope): /pvpc decides.
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

## Per-Pokémon loop (by hand)

The list filtered to IVC. Work on the first tile still named after its species. Renamed ones never match a species name.

1. **Open it.** Tap `tile N`. `$P/ui.py read` must say `detail`.
2. **Read it.** Note the following from the detail screen:
   - Shadow: there's a PURIFY button.
   - Lucky: there's a "LUCKY POKÉMON" line.
   - Size: the XXL or XXS badge over the height.
3. **Moves.** Only if `ivc.py elite <species>` lists moves.
   - Drag up from the weight (the `kg` number) to find the moves under GYMS & RAIDS.
   - Then drag back down from where the weight ended up.
   - Never tap NEW ATTACK.
4. **Appraise.** Tap `menu`, then `APPRAISE`, then `dialog`. `read` gives the bars.
   - Check the bars against CP and HP with `$P/pvp.py check <species> <cp> <hp> -1 --near a/d/h`.
5. **Act.** Run `ivc.py name ...`.
   - Name: rename it the same way /pvpc does. Keep the IVC tag.
   - Check the PvP rule first: `$P/pvp.py rank <species> <a> <d> <h>`.
   - NOPE: in TAG, untick IVC, tick Nope, then tap DONE. If PvpC is ticked too, only untick IVC. PvP candidate: same, but tick PvpC.
6. Tap `close` to go back to the list.
