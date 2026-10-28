---
name: cleanup
description: Cleanup rules for Pokémon GO run on the phone. First rule: purify every shadow tagged Nope, then transfer them in one go. After trading: tag the PvpC1/PvpC2/IV Check shortcuts, power up Clean Trades ones sitting right under an XL-transfer tier, tag Clean Trades Transfer. Tag every Nope GIV, XLX or Transfer (tradeable.py tag --nope). Use when the user says /cleanup, asks to purify and transfer their Nope shadows, to sort their Nope pile, or to clean up after trading.
model: claude-sonnet-5-5
---

# /cleanup — cleanup rules

Uses the shared tapper and screen reader from /pvpc (`~/.claude/skills/pvpc`: `ui.py`, `run.py`, `search.py`).
`S=~/.claude/skills/cleanup`.
Search terms and their bugs: `~/.claude/skills/pvpc/SEARCH.md`. Read it before building a search.

## Shadows in Nope: purify, then transfer

`caffeinate -dimsu python3 $S/shadows.py [--limit N]`

1. Checks that `#Nope&purified` is empty. If it isn't, it stops. Otherwise the bulk transfer could take older purified ones.
2. Searches `#Nope&shadow&!shiny&!costume`. The bar has to read back exactly, because one lost `!` would flip the filter.
3. Opens the first one. It purifies it only if all of these hold:
   - its only tag is Nope
   - no star
   - no XXL/XXS in the name
   - not legendary, mythical or an Ultra Beast (checked by its candy)
   - enough candy and Stardust
   - its appraisal reads under 98% once purified (a wrong name can land a 98% one in Nope). Trade retagging checks this too.
   Anything else is passed over, and it swipes to the next one.
4. Purify: one PURIFY tap, then a check that the dialog names this Pokémon, then one YES tap. It waits until PURIFY is gone, POWER UP is back and the CP has changed (about 13s of animation). It never taps twice: POWER UP moves into PURIFY's spot.
5. After a purify, the swipe stops working, because it no longer fits the search. So it goes back to the list and opens the top tile again.
6. At the end it searches `#Nope&purified`, long-presses a tile, then taps SELECT ALL. It transfers only if `TRANSFER (n)` and the dialog's "transfer n" both equal the number this run purified. If not, it leaves multi-select and stops.

`--limit N` purifies at most N, then transfers those.
If a run stops after purifying, run `python3 $S/shadows.py transfer $S/runs/<time>` to transfer what it purified (`purified.json`).
Each run writes `runs/<time>/log.txt` with timings for every step.

**Android phone:** put `POGO_PHONE=android` in front. See the **Android phone** section of the /pvpc skill.
**iPhone:** same code path (taps go through the Mac helper). Multi-select (long press, SELECT ALL, TRANSFER (n)) and the swipe haven't been tried on the iPhone yet. Run `--limit 1` first and watch.

## Timing (Pixel, 2026-10-08)

About 20–25s per Pokémon: ~13s is the game's purify animation, ~2s to the dialog, ~4–7s back to the list and into the next one. The bulk transfer takes ~2s for the lot.

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

Tagging a shortcut: its search + `&!#<tag>`, long press a tile, SELECT ALL, TAG (n). The n must equal the search's count, and the sheet must say "TAG n POKÉMON". The tag row is found by scrolling the sheet in small steps. Afterwards the same search must come back empty.
PvpC1 and PvpC2 get no `&!#PvpC`: their own search already leaves out anything tagged. On the Pixel, HashTagAJay's PvpC1 search also fills the bar, so nothing more can be typed after it.

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

## Nope: the same tags for everything tagged Nope, on both accounts

The rule (2026-10-25): anything in Nope gets the Tradeable tags, judged for the other account (the one it would be traded to). Nope comes off once its new tag is on.

`POGO_PHONE=android caffeinate -dimsu python3 $S/tradeable.py tag --nope [--limit N]`, either account signed in:

1. It runs `rescue.py` first. A 98%+ one in Nope gets the star and loses Nope, so it never gets a tag here.
2. **Suspects** (2026-10-26): an untraded Nope one that may still belong in its species' top IV or PvP spots. It still has an /ivc name or a `Pvp` name, or it's 93%+. Every gym defender in Nope is a suspect too, traded or not, whatever its name or IVs (2026-10-27): it may be top 20 CP or top 20 IV of its species (/ivcsort's gym rule). It's judged again every run, because its rank moves as the pool changes. The pile is `#Nope&!traded,113,143,202,242,289,977&...` (`,` binds tighter than `&`, so: Nope and (untraded or a gym defender)). `suspects.py` judges each one in place, with the /ivcsort and /pvpc rules against what the account owns now:
   - Still belongs: star on, Nope off (PvpC on for a PvP keeper, and its /ivc or Pvp name if it had none). No other tag. CyrillJan doesn't play PvP, so it keeps a Nope for PvP only if a slot is top 20 of all 4,096 IVs and the form is viable in that league (PvPoke's top 100 there, from `pvp.py update`'s `rankings.json`). Master League doesn't count: it wants perfect IVs, so the IV side covers it.
   - Falls out: the nickname goes blank, so the game shows the species name. That means checked and cleared. It stays in Nope and gets the tags below.
   - Can't tell (a branching line, a missing search, an unreadable tile): nothing is tagged. `tag --nope` lists them and stops. Sort those by hand, then run it again.
   One walk of the pile opens each suspect once: read, judge, then keep or clear it before closing it. It skips the appraisal when it can: a suspect read in an earlier run (`runs/reads-<trainer>.json`, same HP) or an /ivc name that settles it. A name settles it when the `4attack`, `4defense` and `4hp` searches agree with its capitals, the species is pinned, and no IVs the name allows have a PvP slot that counts. The pool searches for ones read before are typed first. A new one waits for its pool searches and is changed in a second walk.
   Already-cleared ones with a species name are remembered in `runs/checked-<trainer>.json`, so a rerun doesn't appraise them again (gym defenders aside: `reads-<trainer>.json` saves their appraisal). `suspects.py --dry-run` judges and writes `suspects.txt` without changing anything.
3. **Traded** Nope: Transfer, Nope off. It can't trade again, so it gets no other tag (and no XLX: that's for untraded ones to trade away). It waits for the suspects, so a traded gym defender in its species' top 20 is kept first.
4. **Untraded** Nope: the first tag that fits wins. HashTagAJay: GuaranteedLucky > Old > medal GIV > 2XL > GIV / XLX > Transfer. CyrillJan: GuaranteedLucky > Luckydex > Old > Reroll > GIV / XLX > Transfer. **Old** = caught 300+ days ago (`age300-`). Every Tradeable step runs, with `#Nope&!traded&...` typed in place of the `Tradeable` shortcut. The tagged ones keep Nope until the end, because the walks find them by it. Then Nope comes off everything with a new tag.

Never touched (they stay Nope): shadows (`shadows.py` does those), lucky, costumes, backgrounds, special trades, and anything that also has IVC, PvpC, Old, GuaranteedLucky or Evo. An untraded catch from 2016-2020 (not special) gets GuaranteedLucky and loses Nope: a trade makes it lucky. That pass runs right after the traded Transfer pass.

Which plan it uses goes by who's signed in:

- **CyrillJan's Nope** goes to HashTagAJay: the normal `plan`, the same rules as the Tradeable pile.
- **HashTagAJay's Nope** goes to CyrillJan: `python3 $S/tradeable.py plan --to CyrillJan`. CyrillJan isn't a completionist account. It only wants good raid attackers and Candy XL, so there's no Luckydex, Reroll or ★100% rule. The GIV (evolved) rule does run (stage 2, a hard stage 1, a gym defender; 2026-10-27), after XLX as above. **GIV**: in DialgaDex's top 6 against some raid boss (`/roster`'s `dialgadex-counters-<date>.json`; no shadows, a mega counts as its species, special trades left out), or an earlier stage of one. Not once CyrillJan has enough: 6 good (3★/4★) copies, or 1 for a species that's only in a top 6 as its mega (a team has one mega), and a Dynamax one of the family if it can Dynamax. After XLX, an untraded Dynamax one also gets GIV if CyrillJan has no Dynamax one of its family. The counts come from CyrillJan's own runs, both only searches: `POGO_PHONE=android caffeinate -dimsu python3 ~/.claude/skills/roster/roster.py count` and `... tradeable.py dynamax` (which families can Dynamax: `dynamax-<date>.json`, from `refresh`). Without them, nothing counts as enough. `plan.md` lists what was left out and why. **XLX**: level 29+ (a power-up costs 5,000 Stardust or more). GIV (far) and Transfer are as above. `read` with CyrillJan signed in adds its 360+ Candy XL families. Without it, none count as full.

HashTagAJay's untraded Nope also gets two passes right after Old (2026-10-27):

- **Medal GIV**: for any other account's Youngster and Fisherman medals. A Rattata (any region; `19&xxs,xs`) of 2.41 kg or less, or a Magikarp (`129`) of 13.13 kg or more. Each one is opened and its weight read. One with no weight read stops the run before 2XL; check those by hand.
- **2XL**: under 360 Candy XL (`countcandyxl0-359`), for a Friendship Friday trade (a sure 2 Candy XL). Nope comes off. It beats every other GIV and XLX, so stage-2 GIV (Crobat) only lands in a family with 360+ Candy XL. A never-traded XXL/XXS one is left out: it gets IVC.

`tag --nope --resort` first puts Nope back on the untraded ones tagged Transfer (and takes Transfer off), so they're judged again under new rules. It also forgets which plan searches already ran. Use it once after a rule change.

HashTagAJay needs the GIV, 2XL, XLX and Transfer tags. `tag --nope` stops if one is missing.

`tag --nope` has never run. `--limit` only caps power-ups: rescue, the traded Transfer pass and every GIV search still run in full. So first count these on each account with `python3 ~/.claude/skills/ivcsort/run.py search "<q>"` (only searches) and show the user:

- `#Nope&traded&!shadow&!lucky&!costume&!background&!#IVC&!#PvpC&!#Old&!#GuaranteedLucky&!#Evo&!gigantamax&!shiny&!legendary&!mythical&!ultrabeast&!#Transfer`: these get Transfer straight away.
- `#Nope&!traded&year2021-&!shadow&!lucky&!costume&!background&!#IVC&!#PvpC&!#Old&!#GuaranteedLucky&!#Evo`: the untraded pile. Next to `#Nope&!traded`, the gap should be the 2016-2020 catches and the kinds left out. 0, or a huge gap, means a term (a tag the account doesn't have, or `year2021-`) isn't read the way it's meant.

On HashTagAJay, also count (print them with `python3 -c "import tradeable as t; print(t.RESORT)"`, and `t.TWO_XL_PILE`, and `t.NOPE_PILE + q + t.NOT_TAGGED` for each `q` in `t.MEDALS`): the `--resort` pile, the two medal piles and the 2XL pile. And `#Nope&#2XL`: it must be 0, or the 2XL pass stops on a tick it didn't expect.

Then `tag --nope --limit 1`, with the user watching.

## XXL and XXS: never Transfer or Nope

The rule (2026-10-22): a Pokémon that was never traded and is XXL or XXS never gets Transfer. It's renamed `XXL` or `xxs` and tagged IVC. `/ivc` counts those names as done, and `/ivcsort` leaves sized IVC ones for the user.

- `tradeable.py tag` does it to its own pile before tagging the rest Transfer. Its Transfer search leaves out never-traded XXL/XXS ones.
- `shadows.py` leaves XXL/XXS shadows out (shadows are never traded).
- `cleantrades.py` and `trades.py` only tag traded ones Transfer, so the rule never applies there.
- `POGO_PHONE=android caffeinate -dimsu python3 $S/sizes.py [--limit N]` sweeps what's already tagged: `#Transfer,#Nope&!traded&xxl`, then `xxs`. Each one is opened and its size badge must agree. Name -> `XXL`/`xxs` (a name that already says its size keeps it). Tags: IVC on, Transfer and Nope off. Run it once per account.

`traded` may miss trades from before Oct 2020 (SEARCH.md), so a very old trade could slip in.
