---
name: pvpc
description: Appraise Pokémon GO Pokémon tagged "PvpC" through iPhone Mirroring, work out their PvP stat-product ranks, and rename them (top 100) or swap the tag to "Nope". Use when the user says /pvpc or asks to process their PvpC Pokémon.
model: claude-sonnet-5-5
---

# /pvpc — rank and rename PvpC Pokémon

Drive Pokémon GO on the user's iPhone through **iPhone Mirroring**. Computer use does the clicking. Everything else goes through `ui.py`, which reads the Mirroring window as text. **Don't take screenshots or zoom** unless a step below says to, or `ui.py` says it can't read something.

- `S=~/.claude/skills/pvpc`, `L=~/PoGO-inventory-scripts/skills/shared` (the shared library: everything but `run.py`)
- Search terms and their bugs: `$L/SEARCH.md`. Read it before building a search.
- `python3 $L/ui.py read` tells you which screen is up and what's on it:
  - `list`: numbered tiles with name and CP.
  - `detail`: name, CP, HP, tags, species ID.
  - `menu`, `appraise-intro`.
  - `gym`: a Pokémon defending a gym (no HP line or tags). Leave it: `tap close` backs out to the list.
  - `appraisal`: IVs from the bars, the candidate rows, and a **VERDICT** line.
  - `tags`: which tags are ticked.
  - `rename`: what's in the nickname box.
  - `unknown`: raw text.
- `python3 $L/ui.py tap <target>` prints `x y` to click, in screenshot coordinates.
  - The spot is randomly fuzzed inside the button.
  - It re-reads the live screen every time.
  - It refuses (non-zero exit, `REFUSED: ...`) if the target isn't there, or if the spot is near Transfer, Power Up, Evolve, Purify, and so on.
  - Targets: `tile N`, `menu`, `close`, `dialog`, `pencil`, `field`, `APPRAISE`, `TAG`, `DONE`, `OK`, `CANCEL`, `PvpC`, `Nope`.
  - **Click exactly the `x y` it printed.** Never make up or reuse coordinates.
- `python3 $L/pvp.py check <species_id> <cp> <hp> <stars|-1> [--near a/d/h]` is the ranker. `ui.py read` runs it for you on the appraisal screen. Run `python3 $L/pvp.py update` if a species is missing.
- Chain commands to save round trips. For example, `ui.py read && ui.py tap menu` reads the screen and plans the next tap in one call.

## Unattended mode

`run.py` does the whole loop below with no Claude: `caffeinate -dimsu python3 $S/run.py [--limit N] [--dry-run]`.
It starts from any screen, Pokémon GO closed too (`home.py`, shared by every script: see below).
It skips anything unsure (logged in `$S/runs/<time>/`) and stops on anything unexpected.
A Pokémon with a name you gave it (`L35`) gets its species from the appraisal's "This Meditite was caught on …" line. If a tap lands on the wrong screen mid-Pokémon, it backs out to the list and passes that one (up to 15 times a run, never from the tag sheet or the nickname box).
At the end of the list it runs the read-only fallen-out step.
If earlier runs stopped before their fallen-out step (a stop, a crash, Ctrl-C), the run that reaches the end adds their new names to its own `renamed.json` first, so one fallen-out step covers them all. It looks back to the last run that has a `fallen.json`, at most 12 hours, and logs which runs it took (also in `carried.json`).
Use this skill to clear its skips by hand.
`caffeinate -dimsu python3 $S/run.py keepers [--limit N]` finishes keepers that older runs left in the PvpC list (a `Pvp ...` name): star on, PvpC off. It passes anything else.

### One front door: pogo.py

`~/PoGO-inventory-scripts/pogo.py` runs any skill's script by step name, and several in a row with `+` between them. A step takes the same args as its script. `python3 ~/PoGO-inventory-scripts/pogo.py list` shows every step.

- `POGO_PHONE=android caffeinate -dimsu python3 ~/PoGO-inventory-scripts/pogo.py pvpc --limit 5 + ivc --limit 5`
- `last` is the run folder an earlier step of the same skill folder made: `pogo.py ivc + ivc fallen last`.
- The whole chain is checked before step 1. It stops at the first step that doesn't end well, with that step's exit code.
- Each step is its own python3 process. The phone stays up between steps and is closed once at the end.

### Starting from anywhere

Every script (`/pvpc`, `/ivc`, `/cleanup`, `/trade`, `/gift`, `/dex`, `/roster`) first runs `home.start()`. The phone can be on any screen.
- First `session.ready()`. iPhone: opens iPhone Mirroring if it isn't open and waits for it to connect (quits and opens it once more if it can't reach the iPhone). Android: wakes the phone and unlocks it. A phone with a PIN needs the PIN in `~/.config/pogo/android-pin` (digits only, one line, `chmod 600`; outside the repo, so it's never committed). A wrong PIN is typed once, then the run stops: more tries lock the phone out.
- At the end of every run that used the phone (finished, stopped, crashed or Ctrl-C), `session.main()` quits iPhone Mirroring or locks the Pixel. `POGO_KEEP_OPEN=1` leaves it as it is. `python3 $L/session.py open|close` does just this part.
- Android: opens Pokémon GO if it isn't in front. Waits out the loading screens. Presses Back on popups and on screens the scripts don't use, until the map or the Pokémon screens show (at most 12 Backs). "Exit Pokémon GO?" gets CANCEL. A locked phone with no PIN file, a sign-in screen or an "isn't responding" box stops the run with a message.
- iPhone: on the iPhone's home screen (told by the game's icon in the dock: app names are hidden), or a screen it doesn't know, it goes home and taps the game in the dock (once). A popup it still doesn't know stops the run: there's no Back key.
- A nickname box left open gets CANCEL (nothing saved). A tag sheet left open: DONE if something is ticked, stop if nothing is.
- `POGO_PHONE=android python3 $L/home.py` does just this step.

### Switching accounts (Pixel)

`POGO_PHONE=android python3 $L/account.py [HashTagAJay|CyrillJan]` (or `pogo.py account ...`) signs the Pixel's game out and back in with the other Google account (or the one named; nothing happens if it's already on). The way: main menu -> Settings gear -> scroll to the bottom -> Sign Out -> YES -> RETURNING PLAYER -> Sign in with Google -> the account's row in Google's picker. It reads the trainer name after to be sure. Started on the sign-in screen, it signs in (an account name is a must then). `--who` only says who's on.
- Which Google account is which trainer: `~/.config/pogo/accounts.json` (`{"HashTagAJay": "...", "CyrillJan": "..."}`), outside the repo.
- Every tap lands at a random spot near its target, held 45-120 ms, drifting 1-6 px like a thumb. Swipes start, slant and move at random. Waits vary.
- Google asking to verify (or any screen it doesn't know after signing out) stops the run: sign in by hand.
Taps come 0.1–0.25s apart (same as /ivc). A short 0.7–1.3s pause stays, on the appraisal only.

### Fallen out and trims

A new Pvp name can push an older Pvp Pokémon out of the top. Per league (L/G/U) and per form, only the best one owned keeps its place. Ties keep.
- **Trim:** beaten in some of its slots but still best in others. It gets renamed to show only the leagues it's still best in (same name rules). It keeps its star. New Pokémon from this run get trimmed too if an older one beats them.
- **Fallen out:** beaten in every top-100 slot it has.
- **Chain:** a name with no room for a league drops it and adds `+`. A trim can make room for it again. That league can then beat a different Pokémon, which gets trimmed or falls in turn. `act-fallen` goes round until nothing changes (at most 8 rounds; it logs `STILL CHANGING` if it hits that).

- `caffeinate -dimsu python3 $S/run.py fallen <run dir>`: reads only. Types a dex-number search for each line a new name landed in (`renamed.json`), reads every tile, writes `fallen.json` and `fallen.txt`, then sorts the fallen ones into groups. `fallen.txt` lists the likely fallen and the trims. Final names come after the appraisal. Starts again where it stopped.
- `caffeinate -dimsu python3 $S/run.py act-fallen <run dir> [--limit N]`:
  1. Appraises every Pokémon that something beats, to see all its slots, including ones its name had no room for (`truths.json`). New Pokémon from this run were appraised already.
  2. Does the rest in that same open when the answer can't change any more. Beaten everywhere: tagged right there (a slot lost to an appraised one stays lost). A trim: renamed right there if nothing else in its line still waits for an appraisal; else it waits and gets renamed once they're all appraised. Repeats if that changed anything. Logged in `tagged.json`.
  3. Tags the ones beaten everywhere that step 2 couldn't (one that wasn't a likely fallen one in `fallen.txt`, or a new name from this run). Same rules as /ivc (shared `fallen.py`): not traded + caught 2016–2020 → GuaranteedLucky, not traded + older than 300 days → Old, else star off + Nope. PvpC gets unticked. Its name gets cleared (the species name shows again), so the Nope recheck doesn't pick it up later.
  - Shiny and costume ones are never tagged. They can still be trimmed (a rename only).
  - `--limit` counts renames and tags together. Appraisals don't count. The door's searches for every likely fallen one run first, even with `--limit 1`.
- Never trimmed or fallen: lines that branch (Eevee aside). Their names can't be read back to one form. A name whose letter two forms share (Charmander and Charmeleon are both `m`) counts that slot as unbeatable until it's appraised.
- Only lines a new name landed in get looked at. A `+` name elsewhere can still hide a better slot.
- Shared code: `search.py` (in-game search, list walking) and `fallen.py` are used by /ivc too. The tapper every skill uses is `skills/shared/base.py`; `run.py` is /pvpc's own walk.

## Android phone (Pixel)

Everything above also works on an Android phone over USB. Set `POGO_PHONE=android` on every command (`ui.py`, `run.py`).
Without it, the scripts drive iPhone Mirroring exactly as before.

- Setup, once: turn on USB debugging (Settings > About phone > tap Build number 7 times, then Settings > System > Developer options). Plug in, tap **Allow** on the phone. Write the phone's PIN to `~/.config/pogo/android-pin` so the scripts can unlock it (see "Starting from anywhere").
- `POGO_PHONE=android python3 $L/android.py check` checks the phone is plugged in and awake, and that Pokémon GO is in front. The scripts don't need it: they open the game themselves. The scripts see the phone with its own screenshots (`adb exec-out screencap`), about 1.5s per look. Don't use scrcpy or any Mac window grab to see the phone: scrcpy's picture freezes now and then while the Mac is in use. `POGO_SCRCPY=1` turns the old scrcpy window back on, only if asked.
- Taps and typing go through adb, so the Mac's mouse and keyboard stay free. Skip the **Session start** steps (no computer use, no `calib`).
- By hand: use `ui.py press <target>` instead of `tap` + click. It plans the same safe spot and taps it on the phone. Type with `android.py type "<name>"`. Clear a text box with `android.py key clear`.
- Unattended: `POGO_PHONE=android caffeinate -dimsu python3 $S/run.py ...`.
- Not tested on a real phone yet (built 2026-10-07). The screen positions were tuned on the iPhone. Try `--limit 1` first and watch.

## Session start

1. `request_access` for iPhone Mirroring, then `open_application` it.
2. Take **one** screenshot. Pick an empty spot on it, `mouse_move` there, then run `python3 $L/ui.py calib <x> <y>`. That teaches the script how screenshot coordinates map to the screen.
   - Redo this if the display resolution changes.
   - Moving the Mirroring window doesn't need a redo. The window is found fresh every call.
3. If a click reports that the desktop is frontmost, `open_application` iPhone Mirroring again and retry.

## Rules

- **Qualifies** = top 100 stat product in any of: Little Cup (500 CP), Great League (1500), Ultra League (2500). Max level 50 (no best buddy).
  - Only leagues its level still fits. Evolving keeps the level and nothing powers down, so a form whose CP at its level now is already over the cap doesn't count there (a CP530 Doduo has no Little Cup slot).
- **Qualifies:** rename it, then star it and remove PvpC (like /ivc's Keep). PvpC is only the to-do pile.
- **Doesn't qualify:** its final tag at the door (`../shared/door.py`: GIV, XLX, Transfer ...; not sure = left as is, on the not-sure list). If it's 98%+ (a shadow: once purified), swap PvpC for IVC so /ivc names it. Don't rename. If it also has IVC, only remove PvpC: /ivc decides.
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
- **Tyrogue:** its highest IV picks what it becomes: Attack Hitmonlee, Defense Hitmonchan, HP Hitmontop. Only that one is ranked, so the name is about the Hitmon it will really be. A tie for highest can go either way (the game picks at random): then it still branches, and the script skips it for a human.
- **Pikachu:** costumed Pikachus have Pikachu's base stats, so they rank the same. They're all checked as plain `pikachu`.

The script applies all of this. If it prints a note about any other branching family (for example Applin into Flapple, Appletun, or Dipplin), ask the user which final evolution the letter should be compared to.

Example: Charmander 0/11/15 gives `PvpL9Gm15U35`.

## Per-Pokémon loop

Start from the inventory filtered to the PvpC tag. Processed Pokémon drop out of the list (Nope, or renamed: star on, PvpC off). A tile whose name starts with `Pvp` is a keeper from before that rule: pass it (`run.py keepers` finishes those). So the next one to do is the first tile whose name doesn't start with `Pvp`. If every visible tile starts with `Pvp`, scroll down over the Mirroring window with computer use and `read` again. If the list stops changing, you're done.

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
   - **NOPE:** never tick Nope by hand. Leave it for `run.py`, whose door gives the final tag. If `[x] IVC` shows, untick only `PvpC`.
   - **Rename:** tap `pencil`, then `field`. Then, in one `computer_batch`: `cmd+a`, `delete`, wait 0.3s, then type the name.
     - Typing straight after cmd+a once dropped the first letter.
     - `read` must show `rename field='<exact name>'`. Then tap `OK`.
     - `read` must show the new name on the detail screen.
     - Tap the star if it's empty. Then tap `menu`, `TAG`, untick `PvpC`, `DONE`.
6. Tap `close` to go back to the list. Next Pokémon.

## Safety

- Never tap Transfer, Power Up, Evolve, Mega Evolve, or Purify. `ui.py tap` refuses them and anything close to them. Don't work around a REFUSED. Take a screenshot and look instead.
- If `read` says `unknown`, or shows a popup you didn't expect, stop. Take a screenshot. Don't confirm anything you didn't mean to.
- Report back to the user after each rename, unless they've said to keep going.
- Tags, the star and the name only change the Pokémon that was opened. The scripts check its CP, max HP, weight and height before and after each change (`still_opened()` in `run.py`). A stray swipe slides the detail screen to the next Pokémon. If that happens, the script stops and names the CP of the one on screen. Check that one by hand.
