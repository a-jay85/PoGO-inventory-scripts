---
name: pvpc
description: Appraise Pokémon GO Pokémon tagged "PvpC" through iPhone Mirroring, work out their PvP stat-product ranks, and rename them (top 100) or swap the tag to "Nope". Use when the user says /pvpc or asks to process their PvpC Pokémon.
model: claude-sonnet-5-5
---

# /pvpc — rank and rename PvpC Pokémon

Drive Pokémon GO on the user's iPhone through **iPhone Mirroring**. Computer use does the clicking. Everything else goes through `ui.py`, which reads the Mirroring window as text. **Don't take screenshots or zoom** unless a step below says to, or `ui.py` says it can't read something.

- `S=~/.claude/skills/pvpc`
- Search terms and their bugs: `$S/SEARCH.md`. Read it before building a search.
- `python3 $S/ui.py read` tells you which screen is up and what's on it:
  - `list`: numbered tiles with name and CP.
  - `detail`: name, CP, HP, tags, species ID.
  - `menu`, `appraise-intro`.
  - `appraisal`: IVs from the bars, the candidate rows, and a **VERDICT** line.
  - `tags`: which tags are ticked.
  - `rename`: what's in the nickname box.
  - `unknown`: raw text.
- `python3 $S/ui.py tap <target>` prints `x y` to click, in screenshot coordinates.
  - The spot is randomly fuzzed inside the button.
  - It re-reads the live screen every time.
  - It refuses (non-zero exit, `REFUSED: ...`) if the target isn't there, or if the spot is near Transfer, Power Up, Evolve, Purify, and so on.
  - Targets: `tile N`, `menu`, `close`, `dialog`, `pencil`, `field`, `APPRAISE`, `TAG`, `DONE`, `OK`, `CANCEL`, `PvpC`, `Nope`.
  - **Click exactly the `x y` it printed.** Never make up or reuse coordinates.
- `python3 $S/pvp.py check <species_id> <cp> <hp> <stars|-1> [--near a/d/h]` is the ranker. `ui.py read` runs it for you on the appraisal screen. Run `python3 $S/pvp.py update` if a species is missing.
- Chain commands to save round trips. For example, `ui.py read && ui.py tap menu` reads the screen and plans the next tap in one call.

## Unattended mode

`run.py` does the whole loop below with no Claude: `caffeinate -dimsu python3 $S/run.py [--limit N] [--dry-run]`.
It skips anything unsure (logged in `$S/runs/<time>/`) and stops on anything unexpected.
At the end of the list it runs the read-only fallen-out step, then quits iPhone Mirroring. Stops, crashes and `--limit` leave it open.
Use this skill to clear its skips by hand.
Taps come 0.1–0.25s apart (same as /ivc and /ivcsort). A short 0.7–1.3s pause stays, on the appraisal only.

### Fallen out and trims

A new Pvp name can push an older Pvp Pokémon out of the top. Per league (L/G/U) and per form, only the best one owned keeps its place. Ties keep.
- **Trim:** beaten in some of its slots but still best in others. It gets renamed to show only the leagues it's still best in (same name rules). It keeps PvpC. New Pokémon from this run get trimmed too if an older one beats them.
- **Fallen out:** beaten in every top-100 slot it has.
- **Chain:** a name with no room for a league drops it and adds `+`. A trim can make room for it again. That league can then beat a different Pokémon, which gets trimmed or falls in turn. `act-fallen` goes round until nothing changes (at most 8 rounds; it logs `STILL CHANGING` if it hits that).

- `caffeinate -dimsu python3 $S/run.py fallen <run dir>`: reads only. Types a dex-number search for each line a new name landed in (`renamed.json`), reads every tile, writes `fallen.json` and `fallen.txt`, then sorts the fallen ones into groups. `fallen.txt` lists the likely fallen and the trims. Final names come after the appraisal. Starts again where it stopped.
- `caffeinate -dimsu python3 $S/run.py act-fallen <run dir> [--limit N]`:
  1. Appraises every Pokémon that something beats, to see all its slots, including ones its name had no room for (`truths.json`). New Pokémon from this run were appraised already.
  2. Once they're all appraised, renames the trims. Repeats if that changed anything.
  3. Tags the ones beaten everywhere. Same rules as /ivcsort (shared `fallen.py`): not traded + caught 2016–2020 → GuaranteedLucky, not traded + older than 300 days → Old, else star off + Nope. PvpC gets unticked.
  - Shiny and costume ones are never tagged. They can still be trimmed (a rename only).
  - `--limit` counts renames and tags together. Appraisals don't count: even `--limit 1` first opens and appraises every beaten one in each line (that changes nothing).
- Never trimmed or fallen: lines that branch (Eevee aside). Their names can't be read back to one form. A name whose letter two forms share (Charmander and Charmeleon are both `m`) counts that slot as unbeatable until it's appraised.
- Only lines a new name landed in get looked at. A `+` name elsewhere can still hide a better slot.
- Shared code: `search.py` (in-game search, list walking) and `fallen.py` are used by /ivcsort too. `run.py` is the shared tapper for /ivc and /ivcsort.

## Android phone (Pixel)

Everything above also works on an Android phone over USB. Set `POGO_PHONE=android` on every command (`ui.py`, `run.py`).
Without it, the scripts drive iPhone Mirroring exactly as before.

- Setup, once: turn on USB debugging (Settings > About phone > tap Build number 7 times, then Settings > System > Developer options). Plug in, tap **Allow** on the phone. Also turn on **Stay awake** in Developer options: adb can't get past a lock screen.
- `POGO_PHONE=android python3 $S/android.py check` checks the phone is plugged in and awake, and that Pokémon GO is in front. The scripts see the phone with its own screenshots (`adb exec-out screencap`), about 1.5s per look. Don't use scrcpy or any Mac window grab to see the phone: scrcpy's picture freezes now and then while the Mac is in use. `POGO_SCRCPY=1` turns the old scrcpy window back on, only if asked.
- Taps and typing go through adb, so the Mac's mouse and keyboard stay free. Skip the **Session start** steps (no computer use, no `calib`).
- By hand: use `ui.py press <target>` instead of `tap` + click. It plans the same safe spot and taps it on the phone. Type with `android.py type "<name>"`. Clear a text box with `android.py key clear`.
- Unattended: `POGO_PHONE=android caffeinate -dimsu python3 $S/run.py ...`.
- Not tested on a real phone yet (built 2026-10-07). The screen positions were tuned on the iPhone. Try `--limit 1` first and watch.

## Session start

1. `request_access` for iPhone Mirroring, then `open_application` it.
2. Take **one** screenshot. Pick an empty spot on it, `mouse_move` there, then run `python3 $S/ui.py calib <x> <y>`. That teaches the script how screenshot coordinates map to the screen.
   - Redo this if the display resolution changes.
   - Moving the Mirroring window doesn't need a redo. The window is found fresh every call.
3. If a click reports that the desktop is frontmost, `open_application` iPhone Mirroring again and retry.

## Rules

- **Qualifies** = top 100 stat product in any of: Little Cup (500 CP), Great League (1500), Ultra League (2500). Max level 50 (no best buddy).
- **Qualifies:** rename it. Keep the PvpC tag.
- **Doesn't qualify:** remove PvpC, add Nope. If it's 98%+ (a shadow: once purified), never Nope: swap PvpC for IVC so /ivc names it. Don't rename. If it also has IVC, only remove PvpC (no Nope): /ivc decides.
- **Name format:** `Pvp` then leagues in order L, G, U, like `Pvp G1`, `Pvp G35 U88`, `Pvp L5G7U99`. Max 12 characters.
  1. Keep all spaces if it fits.
  2. Else drop spaces between leagues.
  3. Else also drop the space after `Pvp`.
  4. Else drop the league with the worst rank number, add `+` to the end, and try again.
- **Which form counts:** for each league, use the best-ranking form in the Pokémon's family (itself or any evolution). Little Cup only counts the Pokémon itself, and only if it's unevolved and can evolve.
- **Lower-evolution letter:** if the best form for a league is not a final evolution, add one lowercase letter after the league letter. The letter is the first letter of that form's name that differs from the final evolution. Charmeleon vs Charizard gives `m`, so `Gm15`. Magneton vs Magnezone gives `t`.
- **Plus sign:** add `+` if some other lower (non-final) evolution also makes top 100 but isn't what's shown. Only one `+` ever.
- Names on older Pokémon that leave out leagues are intentional (a better one exists). By hand, don't touch them. `act-fallen` keeps them right.

- **Eevee:** every form gets a letter, finals included: Eevee `N`, Vaporeon `v`, Jolteon `j`, Flareon `f`, Espeon `e`, Umbreon `u`, Leafeon `l`, Glaceon `g`, Sylveon `s`. Pick top-100 entries best rank first, whatever the league. Add as many as fit, written in league order (L, G, U). If some don't fit, the last one that fit makes way for a `+`. Example: 15/11/14 gives `PvpGN45Uu28+`.
- **Pikachu:** costumed Pikachus have Pikachu's base stats, so they rank the same. They're all checked as plain `pikachu`.

The script applies all of this. If it prints a note about any other branching family (for example Applin into Flapple, Appletun, or Dipplin), ask the user which final evolution the letter should be compared to.

Example: Charmander 0/11/15 gives `PvpL9Gm15U35`.

## Per-Pokémon loop

Start from the inventory filtered to the PvpC tag. Processed Pokémon drop out of the list (Nope) or keep their tag (renamed). So the next one to do is the first tile whose name doesn't start with `Pvp`. If every visible tile starts with `Pvp`, scroll down over the Mirroring window with computer use and `read` again. If the list stops changing, you're done.

Every "tap X" below means: run `ui.py tap X`, then click the printed spot. After each click, the next `ui.py` call reads the new screen. Wait about 1 second after a click before reading (`sleep 1 && ...`).

1. **Open it.** `ui.py read` on the list, then tap `tile N`.
2. **Read it.** `ui.py read` must say `detail` with a name, CP, HP and exactly one species ID.
   - It saves these for step 4.
   - Forms are told apart by the type line first (Rattata is Normal, Alolan Rattata is Dark/Normal). Forms with the same stats in the whole family count as one (Oricorio).
   - Several IDs left with different stats (Pumpkaboo sizes): run `pvp.py check` for each in step 4. Drop the ones that say `NO MATCH`. If the rest all give the same name, use it. If not, ask the user.
   - If species shows `?`, work out the right ID yourself. Then run `pvp.py check` by hand in step 4.
3. **Appraise.** Tap `menu`, then `APPRAISE`, then `dialog`. The intro text goes away and the bars show. After the APPRAISE click, go straight to `sleep 1 && ui.py tap dialog` in one call. No `read` first. The intro always shows, and `tap` re-reads the screen itself.
4. **Decide.** `ui.py read` on the appraisal screen prints the bar IVs (`raw` should be close to whole numbers), the matching rows (`*` = exact bar match), and the VERDICT:
   - `VERDICT: <name>` or `VERDICT: NOPE`: go with it.
   - `NEED BARS` or `NO MATCH`, or a `raw` value near .5 or the error `BARS UNREADABLE`: zoom on the bars once to check.
     - Then run `pvp.py check <species> <cp> <hp> -1 --near a/d/h` with your reading.
     - Still unclear: stop and ask the user.
5. **Act.** Tap `dialog` to close the appraisal (`read` should say `detail`).
   - **Nope:** tap `menu`, then `TAG`.
     - `read` shows the ticks. Tap `PvpC` to untick it, then tap `Nope` to tick it. If `[x] IVC` shows, untick only `PvpC`, tap `DONE`, and skip the next two checks.
     - `read` must show `[ ] PvpC` and `[x] Nope`. Then tap `DONE`.
     - `read` must show `tags=['Nope']` on the detail screen.
   - **Rename:** tap `pencil`, then `field`. Then, in one `computer_batch`: `cmd+a`, `delete`, wait 0.3s, then type the name.
     - Typing straight after cmd+a once dropped the first letter.
     - `read` must show `rename field='<exact name>'`. Then tap `OK`.
     - `read` must show the new name on the detail screen.
6. Tap `close` to go back to the list. Next Pokémon.

## Safety

- Never tap Transfer, Power Up, Evolve, Mega Evolve, or Purify. `ui.py tap` refuses them and anything close to them. Don't work around a REFUSED. Take a screenshot and look instead.
- If `read` says `unknown`, or shows a popup you didn't expect, stop. Take a screenshot. Don't confirm anything you didn't mean to.
- Report back to the user after each rename, unless they've said to keep going.
