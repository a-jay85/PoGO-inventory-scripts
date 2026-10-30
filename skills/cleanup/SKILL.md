---
name: cleanup
description: Cleanup rules for Pokémon GO run on the phone. One-time pass: clear the last Nope pile (nopes.py). After trading: tag the PvpC1/PvpC2/IV Check shortcuts, power up Clean Trades ones sitting right under an XL-transfer tier, tag Clean Trades Transfer. Use when the user says /cleanup, asks to clear their Nope pile, or to clean up after trading.
model: claude-sonnet-5-5
---

# /cleanup — cleanup rules

Uses the shared tapper and screen reader: the shared library (`~/PoGO-inventory-scripts/skills/shared`: `base.py`, `ui.py`, `search.py`).
`S=~/.claude/skills/cleanup`.
Search terms and their bugs: `~/PoGO-inventory-scripts/skills/shared/SEARCH.md`. Read it before building a search.

## The last Nope pile: nopes.py (once per account)

Nothing tags Nope any more (2026-10-29). /ivc, /ivcsort and /pvpc give the final tag at the door (`../shared/door.py`). `nopes.py` clears what's left in Nope:

`POGO_PHONE=android caffeinate -dimsu python3 $S/nopes.py [--limit N] [--dry-run]`

1. Nope comes off the ones that already have a final tag (GIV, XLX, 2XL, Transfer, Reroll, Luckydex, Old, GuaranteedLucky, Evo, Special).
2. It walks `#Nope` and opens each one:
   - also has IVC or PvpC: Nope off, that skill decides.
   - 98%+ (a shadow: once purified): star on, Nope off.
   - may still be a keeper (93%+, a nickname, or a gym defender): name cleared, IVC on, Nope off. /ivc names it again and /ivcsort judges it.
   - the rest: the door gives its final tag and takes Nope off. Not sure (a shadow, lucky, costume, background ...): Nope stays and it goes on the not-sure list (`../shared/runs/not-sure.json`), so a rerun passes over it. Those stay out of the IV and PvP pools (their searches have `!#Nope`).

`--dry-run` skips step 1 and changes nothing in step 2. Run it on both accounts (`pogo.py account`).

`shadows.py` and `trades.py` hold shared taps now (purify, exact search, tag sheet). Their old Nope walks are gone, and so are `rescue.py` and `suspects.py`.

## After trading: tag the shortcuts, power up for XL, tag Transfer

`POGO_PHONE=android caffeinate -dimsu python3 $S/cleantrades.py [--limit N]`
`POGO_PHONE=android caffeinate -dimsu python3 $S/cleantrades.py --look` reads levels only. It taps POWER UP to read the dialog, then CANCEL. Nothing is spent or tagged.

It works off the saved search shortcuts, always in this order:

1. **PvpC1** and **PvpC2** get the PvpC tag. **IV Check** gets IVC. A shortcut the account doesn't have is skipped (CyrillJan has no PvpC ones). This step goes first. Clean Trades only shows untagged ones (`!#`), so these drop out of it.
2. **Clean Trades** + `&countcandyxl0-359` (under 360 Candy XL). For each one:
   - Its CP and max HP give the levels it could be. If none of them is 14, 19, 22 or 30 (or the half level after), it's skipped with no taps.
   - Otherwise POWER UP is tapped. The dialog's "CP a → b" and Stardust cost narrow the level. The cost changes every 2 levels (5,000 dust = level 29–30.5). Lucky and purified discounts are allowed for.
   - If that still mixes a play with a non-play, it taps + (one more power-up) up to 4 times. Each + shows a new CP and total cost that narrow it more. It never appraises.
   - At 14, 19, 22 or 30 it sets the dialog to the 1 or 2 power-ups needed to reach 15, 20, 23 or 31, and taps POWER UP once. Those are the next XL-on-transfer tiers. The plays come from `~/claude-plans/_reports/personal/pogo/xl-transfer-roi.md`. The dialog's CP after must match the level math first. A "Do you really want to power up" box gets YES.
   - Never below 1,000,000 Stardust. Below that it stops powering up, but still tags.
   - `--limit N` stops after N power-ups. The rest weren't checked, so Clean Trades isn't tagged Transfer then.
3. CyrillJan only: **Clean Trades** + a trade evolution gets the Evo tag. HashTagAJay doesn't need the XP, so there they go to Transfer like the rest. It tells the accounts apart by the storage max over the empty search (`7874 / 7875`): over 10,000 is HashTagAJay (13,000 on 2026-10-22; CyrillJan 7,875). `--look` skips that. The list: Kadabra, Machoke, Graveler (Alolan too), Haunter, Boldore, Gurdurr, Karrablast, Shelmet, Phantump, Pumpkaboo. They evolve free once traded, whatever they were traded for. Not the base forms (Abra...). The search uses dex numbers (`64,67,75,93,525,533,588,616,708,710`): the names make it too long for the bar to read back. `tradeevolve` can't be used: it misses traded ones.
4. **Clean Trades** gets the Transfer tag. It doesn't transfer.

`cleantrades.py evo` runs steps 1 and 3 (step 1 first, or a PvpC one could end up Evo). `cleantrades.py fix` moves old ones from Transfer to Evo: `#Transfer&traded&<the dex numbers>`, untick Transfer, tick Evo. It ran on CyrillJan's Pixel on 2026-10-22 (1 moved, then 0 more once Karrablast and Shelmet were added). Both modes stop on HashTagAJay.

`cleantrades.py transfer [--limit N]` runs step 2's power-up walk on `#Transfer&countcandyxl0-359`, on either account. Run it before transferring the Transfer pile: it catches the ones tagged before every tagger powered up first. Every script that tags Transfer now runs that walk on its pile first (`ct.power_pile`), `tradeable.py tag --nope`'s traded Nope too. A nickname ('96A') gets its species from the candy line and types, or else the appraisal's "This Poochyena was caught" line. On CyrillJan's Pixel on 2026-10-28 it walked all 80 and powered up 7 over four runs.

Tagging a shortcut: its search + `&!#<tag>`, long press a tile, SELECT ALL, TAG (n). The n must equal the search's count, and the sheet must say "TAG n POKÉMON". The tag row is found by scrolling the sheet in small steps. Afterwards the same search must come back empty.
PvpC1, PvpC2 and Clean Trades get no `&!#<tag>`: their own search already leaves out anything tagged. On the Pixel, HashTagAJay's PvpC1 search also fills the bar, so nothing more can be typed after it.

Adding to a shortcut's search: tap the shortcut, tap the filled bar, jump to the end, type the extra part, Return. A `count…` term eats any text after it, so the XL part always goes last.

**iPhone (HashTagAJay):** run it without `POGO_PHONE=android` (it opens iPhone Mirroring itself). Tagging and the jump to the end of the bar (Cmd+Right) ran on 2026-10-19. The power-up walk and the swipe haven't run on the iPhone yet, because none of its Clean Trades were under 360 XL. The first time some are, run `--look`, then `--limit 1`. Shortcut taps often land as a long press there. The script closes the box and taps again.


## Tradeable: tag CyrillJan's trade pile by what it's worth to HashTagAJay

`S=~/.claude/skills/cleanup`. Four steps, in this order:

1. `python3 $S/tradeable.py refresh` (the Mac): PvPoke's top 100s -> `pvp-giv-<date>.json`, and the hard evolutions -> `giv-evolved-<date>.json`.
2. `POGO_PHONE=android caffeinate -dimsu python3 $S/tradeable.py read`, HashTagAJay signed in. Only searches. Finds the families with a lucky one and under 348 candy, and those with 360+ Candy XL.
3. `python3 $S/tradeable.py plan` (the Mac): every search to tag, in `runs/<time>-plan/plan.md`. Read it before step 4. It needs HashTagAJay's newest lucky and ★100% /dex runs, /roster's `roster.json` and step 2.
4. `POGO_PHONE=android caffeinate -dimsu python3 $S/tradeable.py tag [--limit N]`, CyrillJan signed in. Tags and powers up.

One tag each, the first that fits:

1. **Luckydex**: HashTagAJay's lucky dex misses it, or an evolution of it (/dex's gender and form rules).
2. **Reroll**: a new copy would be #1 against some raid boss (/roster).
3. **GIV**: a new 100 would fill a hole on HashTagAJay's ★100% page, itself or by evolving (`dex.hundred_useful`, see /dex: a later stage on the page fills the earlier ones, and each missing branch wants its own copy), PvPoke top 100 in Great, Ultra or Master with every rank 1 IV 5+, #2-#6 against some raid boss, or HashTagAJay has a lucky of the family and under 348 candy.
4. **XLX**: level 26+ (a power-up costs 4 Candy or more: 4,000 Stardust with 4 Candy, or 4,500+ Stardust). At 4,000 the Candy decides (3 Candy is level 25-25.5); if it can't be read, it's left for a look by hand. Each one left is opened and read.
5. **GIV (evolved)**: a stage 2, or a stage 1 that takes 100+ candy, a quest or an item (any item, lures too) to evolve into. A stage 1 that GO can't evolve into yet counts too (Kleavor, Alolan Marowak, Alolan Raichu, Hisuian Braviary). Stages count those future evolutions, so Hisuian Typhlosion is stage 2. A baby isn't a stage: Raichu is stage 1. Also the gym defenders (Pokebattler top 6, `GYM_DEFENDERS` in /ivc: Blissey, Chansey, Snorlax, Slaking, Wobbuffet, Dondozo) and every untraded Dynamax one. On CyrillJan's pile, Tandemaus too (`GIV_FOR_TAKER`): HashTagAJay still wants the family of 3 Maushold (2026-10-27). It's tagged after the XLX walk, so a level 26+ one gets XLX instead. The list comes from PokeMiners' game master: `refresh` saves it as `giv-evolved-<date>.json`.
6. **GIV (far)**: never traded and caught 100 km or more away (`!traded&distance100-`), and no other tag fits (2026-10-22).
7. **Transfer**: the rest.

Special trades get no tag at all, not even Transfer, and are never powered up: Legendary, Mythical, Ultra Beast, shiny and Gigantamax. The user trades them by hand, so no tag lines one up to use up the day's special trade (2026-10-23). The plan leaves those species out, and every tag search and walk has `&!gigantamax&!shiny&!legendary&!mythical&!ultrabeast`. One that isn't in HashTagAJay's dex yet is a special trade too: the script can't see that, so check it by hand. A never-traded XXL or XXS one never gets Transfer: it's renamed XXL or xxs and tagged IVC first (see "XXL and XXS" below).

The tag step: the `Tradeable` shortcut + each plan search + the special-trade terms + `&!#Luckydex&!#Reroll&!#GIV`, tagged like a cleantrades pile. Then it walks the tagged ones for power-ups, then the untagged ones for XLX and power-ups, then tags the evolved GIV ones, then tags the rest Transfer.
Power-ups are cleantrades' cheap jumps only (14->15, 19->20, 22->23, 30->31), never below 1,000,000 Stardust. The 360 Candy XL cap counts the account that will transfer it: HashTagAJay for the traded tags, CyrillJan for the rest. Out of Stardust: it goes on with XLX only.
If it can't tell whether one is level 26+ (or doesn't know the species), it tags nothing Transfer and lists those in the log. Tag them XLX by hand (or not), then run `tag` again.
`--limit N` caps the power-ups in each walk. All the Luckydex, Reroll and GIV tagging still runs.

If `read` stops partway, `read runs/<time>-read/searches.json` picks up where it left off.

`read` ran on the Pixel on 2026-10-22. `tag` has never run. First time: `tag --limit 1`, with the user watching (it still tags every plan search).

## XXL and XXS: never Transfer

The rule (2026-10-22): a Pokémon that was never traded and is XXL or XXS never gets Transfer. It's renamed `XXL` or `xxs` and tagged IVC. `/ivc` counts those names as done, and `/ivcsort` leaves sized IVC ones for the user.

- `tradeable.py tag` does it to its own pile before tagging the rest Transfer. Its Transfer search leaves out never-traded XXL/XXS ones.
- `cleantrades.py` only tags traded ones Transfer, so the rule never applies there.
- `POGO_PHONE=android caffeinate -dimsu python3 $S/sizes.py [--limit N]` sweeps what's already tagged: `#Transfer&!traded&xxl`, then `xxs`. Each one is opened and its size badge must agree. Name -> `XXL`/`xxs` (a name that already says its size keeps it). Tags: IVC on, Transfer off. Run it once per account.

`traded` may miss trades from before Oct 2020 (SEARCH.md), so a very old trade could slip in.
