---
description: What every script and shared file can do, one line each (written by codemap.py, don't edit). Every function is in skills/MAP.md.
paths:
  - "skills/**/*.py"
  - "*.py"
---
# What each file can do

Written by `codemap.py` from each file's top comment. Don't edit it: change the comment and run `python3 codemap.py`.
Before writing a helper, grep `skills/MAP.md` (every function, its arguments and what it does) for the thing you need. Code two scripts need lives in `skills/shared/`; import it, never copy it.


## skills/shared
- `skills/shared/account.py`: Switch the Pixel's Pokémon GO between the user's two accounts: sign out, then back in with the other Google account
- `skills/shared/adbwifi.py`: The Pixel over Wi-Fi, so the scripts reach it unplugged
- `skills/shared/advsync.py`: Turn Adventure Sync on for the account signed in
- `skills/shared/android.py`: Android phone for the /pvpc and /ivc scripts
- `skills/shared/base.py`: The shared tapper: screen reading, taps, timing, run folders and logging, and the detail-screen steps (appraise, tags, star, rename) every skill's script uses
- `skills/shared/door.py`: The door: a Pokémon /ivc, /pvpc or /ivc just found isn't a keeper gets its final tag right there (verdict.py), on the detail page that's still open
- `skills/shared/eggs.py`: The Eggs tab: read the eggs, put the mode's one in the free ∞ incubator, and set the hatch timer
- `skills/shared/fallen.py`: Fallen out: older Pokémon that newer, better ones push out of the top
- `skills/shared/home.py`: Start from anywhere: every script calls start() first, so the phone can be on any screen, or Pokémon GO not open
- `skills/shared/pagefacts.py`: What the door needs to know, read off the list tile and the Pokémon's own page instead of searches
- `skills/shared/pages.py`: Whole screens that belong to one script, and the way out of each, for every other script
- `skills/shared/peek.py`: Look at the phone (or a saved png) for as few tokens as possible
- `skills/shared/pokedb.py`: A memory of each account's Pokémon, built from what the scripts already read
- `skills/shared/popups.py`: Boxes the game pops up over any screen, by itself or left over from another script, that one safe tap closes
- `skills/shared/powerup.py`: Powering one Pokémon up: its level from the page and the dialog, and the cheap jumps to the next Candy XL tier
- `skills/shared/pvp.py`: The game master (PvPoke's gamemaster.json): base stats, CP and HP, the level from IVs, CP and HP (level_of), evolutions, and PvP ranks and nicknames
- `skills/shared/raidteams.py`: The raid team rule (the user, 2026-11-17): a Pokémon on its holder's own team of 6 against some 4★+ raid boss, at its real level and IVs (team A, the user's Team …
- `skills/shared/rules.py`: Tag names, rule numbers and species lists that skills and verdict.py (the rule book) use: one copy, here
- `skills/shared/savedsearch.py`: The search list's saved searches: read their labels, run one, add to it, type a long search, and tag everything a search finds (tag_pile: long press, SELECT ALL, tag)
- `skills/shared/search.py`: In-game searches and list walking, shared by /ivc and /pvpc's fallen-out step
- `skills/shared/session.py`: A run's phone from start to end
- `skills/shared/speedtest.py`: Go through a step's motions on the phone and time them, changing nothing: for speed work, where the logic isn't what's tested (the user, 2026-11-17)
- `skills/shared/tagsheet.py`: Shared reads and taps: a search typed until the bar reads back exactly, who's on the detail page (name, CP, HP, weight, height), its tag chips, the caught date at the …
- `skills/shared/taps.py`: Shared taps: the swipe to the next Pokémon, SELECT ALL, an exact search, the Stardust and candy owned, and purify (one PURIFY, one YES, the animation waited out)
- `skills/shared/timer.py`: One local timer for the scripts that run by themselves (gymfeed, hatch, goplus)
- `skills/shared/ui.py`: Screen reader + tap planner for /pvpc
- `skills/shared/verdict.py`: The final tag for a Pokémon that just fell short of a keeper, judged right where it was judged (no Nope)

## skills/cleanup
- `skills/cleanup/cleantrades.py`: Cleanup after trading: tag the saved searches, power up the Clean Trades ones that cross an XL tier, tag them Transfer
- `skills/cleanup/dbfill.py`: Fills the Pokémon database (../shared/pokedb.py) with the IVs of one search's Pokémon: the ones it doesn't know yet get opened and appraised
- `skills/cleanup/dbsweep.py`: Deletes from the Pokémon database (../shared/pokedb.py) the ones a bulk tagger tagged Transfer without opening them (savedsearch.tag_pile)
- `skills/cleanup/leftovers.py`: Tag HashTagAJay's Leftovers saved search by what a trade to another account is worth (CyrillJan, or the user's wife's account, which is further behind: good for any …
- `skills/cleanup/savedsearches.py`: Read the saved searches off the phone and check they hold the terms in rules.SAVED. It only reads: it tags nothing
- `skills/cleanup/sizes.py`: An XXL Pokémon, traded or not, is kept: favorite on, its trade, Transfer and IVC tags off (it has value in showcases, the user 2026-11-04)
- `skills/cleanup/specieswise.py`: Re-judge HashTagAJay's #GIV, #Transfer or #Reroll pile by species alone, with no Pokémon opened (the user, 2026-11-16; #Reroll 2026-11-22, after its raid Rerolls began …
- `skills/cleanup/tradeable.py`: Tag CyrillJan's Tradeable saved search by what a trade to HashTagAJay is worth, and power them up for Candy XL.

## skills/dex
- `skills/dex/dex.py`: /dex: read one Pokédex page and print a storage search of the Pokémon missing from it, for another account to paste
- `skills/dex/luckydex.py`: Put HashTagAJay's missing-lucky list into CyrillJan's saved search Luckydex
- `skills/dex/sizerecords.py`: /sizerecords: read each species' MY RECORDS box off the Pokédex (lightest, heaviest, shortest, tallest), then say which account's record would beat the other's, so a …

## skills/evo
- `skills/evo/evo.py`: Evolve every free trade evolution tagged Evo, as fast as the game lets it

## skills/gift
- `skills/gift/gift.py`: /gift: send San Francisco gifts to every friend who can take one, the most useful first

## skills/goplus
- `skills/goplus/goplus.py`: Connect the GO Plus+: tap its Poké Ball at the top right of the map

## skills/gymfeed
- `skills/gymfeed/gymfeed.py`: Feed berries to the Pokémon in the gyms you're defending, from the gym badge list

## skills/hatch
- `skills/hatch/hatch.py`: /hatch: hatch the eggs that are ready, put the mode's egg in the free ∞ incubator, and set the timer for the next run

## skills/ivc
- `skills/ivc/ivc.py`: IV% nickname maker for the /ivc skill
- `skills/ivc/names.py`: /ivc's names pass (run.py names, and the end of every sort): works through the IVC-tagged list with no Claude
- `skills/ivc/run.py`: Unattended /ivc: keep the best IVC Pokémon (favorite + untick IVC)
- `skills/ivc/sort.py`: Rules for /ivc: which IVC Pokémon to keep (favorite + untag) and which to send to the door (its final tag)

## skills/mega
- `skills/mega/mega.py`: Mega Evolve every Pokémon tagged TODO, once a day each

## skills/pvpc
- `skills/pvpc/run.py`: Unattended /pvpc: works through the PvpC-tagged list in iPhone Mirroring with no Claude

## skills/roster
- `skills/roster/raidteam.py`: /raidteam: the signed-in account's best 6 raid attackers against every raid boss like a 4-star raid's or higher, released or not, two teams each (the user, 2026-11-19): …
- `skills/roster/roster.py`: /roster: HashTagAJay's best 6 raid attackers against every raid boss, and which species a new traded copy would still help with
- `skills/roster/sigmoves.py`: Signature moves not in GO yet (the user, 2026-11-19: future-proofing counts mainline moves too): a damaging move (not Z, not Max) that only one family learns in the main …

## skills/trade
- `skills/trade/phone.py`: One phone for /trade, run as its own process: trade.py starts one for the iPhone and one for the Android phone
- `skills/trade/trade.py`: /trade: local trades between the user's two accounts, regular trades only

## repo root
- `pogo.py`: One front door for every skill's script
- `heal.py`: pogo.py heals: a step that stops or crashes gets fixed, then runs again with only what's left
- `watch.py`: Run a phone script quietly: no output while it runs, a short summary when it ends
- `merge_gate.py`: The merge gate: a PR of this repo merges only when its tests pass, its phone test ran its own code, and its body says which sibling code was checked
- `wt_cleanup.py`: Remove every worktree whose PR has merged
- `codemap.py`: Writes the maps of what every script and shared file can do, from the code alone, so Claude finds a helper that already exists (pvp.level_of, the level from IVs, CP and …
