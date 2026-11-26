# Facts every script shares

This file has no `paths:`, so it loads in every session. It holds what many scripts need, with a pointer to where each rule lives. The code is the source of truth. A fact only one script needs goes in that script's `.claude/rules/<skill>.md`, which loads when its files are read. Before you answer a chat question about a skill without reading its code, Read `.claude/rules/<skill>.md` by hand.

## The two accounts

- HashTagAJay (`rules.TAKER`) is the completionist account: Luckydex, ★100%, the roster. Its pile (saved search Leftovers) is judged for CyrillJan or the user's wife's account.
- CyrillJan (`rules.GIVER`) wants good PvE Pokémon and Candy XL. It has no Luckydex, ★100% or roster. Its pile (saved search Tradeable) is judged for HashTagAJay. Free trade evolutions are for its XP (`rules.EVO_FOR`).
- `~/.config/pogo/accounts.json` says which Google account is which trainer (`skills/shared/account.py`).

## Tags (names in `skills/shared/rules.py`)

- A tag means something different in each storage. `skills/shared/verdict.py` gives the final tag, and the table in `.claude/rules/verdict.md` says what each tag means on each account. Read that table before you explain a tag.
- Reroll: the other account needs a new 100% copy. GIV: the trade is worth it for another reason, mostly the sender's Candy or Candy XL. Luckydex: HashTagAJay's lucky dex is missing it.
- Others: Transfer, Clean Trades, Evo, Old (caught 300+ days ago), GuaranteedLucky (an untraded catch from 2016-2020 turns lucky once traded), 2XL (a Friendship Friday trade), Special, IVC.
- The XLX tag is gone. The user retagged every one as GIV (2026-11-19).

## Game facts the scripts are built on

- A lucky Pokémon can't be traded. When a rule says "lucky", check if it means the Pokémon or a lucky one of its family the other account owns.
- The account that trades a Pokémon away gets 2 Candy (catch places 0-10 km apart), 3 (10-100 km) or 4 (100+ km), plus 1 Candy XL (2 on a Friendship Friday). A transfer gives 1 Candy. (`rules.TRADE_SENDER_CANDY`, `TRADE_SENDER_XL`, `TRANSFER_CANDY`)
- From level 26, a power-up costs 4 Candy or more (`rules.XLX_LEVEL`). Past level 40 it costs Candy XL. Lucky power-ups cost half the Stardust, purified ones 0.9×.
- The scripts' "enough" bars: 360 Candy XL (`rules.XL_CAP`), 348 Candy (`rules.LUCKY_CANDY`).
- An IV sum of 44+ (98% or 100%) is never traded or transferred (`rules.ALWAYS_KEEP`).
- Search terms and their bugs: `skills/shared/SEARCH.md` (always loaded).

## Where the data is

- The Pokémon database: `~/.config/pogo/pokemon.db` (SQLite, `skills/shared/pokedb.py`). Per account it has every Pokémon read (exact IVs, CP, HP, tags), Candy and Candy XL per family, Mega Energy, and the dex size records. Query it, and give the read date, before a phone search or saying "I don't know". `python3 skills/shared/pokedb.py candy [account]` lists Candy, XL and energy. `skills/shared/pokedb.sqlite` is an empty leftover.
- The game master: `skills/shared/gamemaster.json` (PvPoke's). It has base stats, CP and HP, levels and evolutions. `skills/shared/pvp.py` reads it, and `skills/shared/rankings.json` has the PvP ranks. `python3 skills/shared/pvp.py update` downloads both again.
- Raid counters: `skills/roster/dialgadex-counters-*.json`, pulled from DialgaDex (`skills/roster/roster.py`).
- Every function and its comment: `skills/MAP.md`. Grep it before writing a helper.

## The user's raid team names

- Team Future: DialgaDex's #1 mega and #1 other attacker per 4★+ boss, unreleased ones too (`roster.ideal_firsts()`). Same for every account.
- Team Ideal: the same, only what's in GO today (`roster.ideal_firsts(roster.COUNTERS)`). When the user means "what to collect today", it's likely this one.
- Team Available: one account's own copies at today's levels and IVs (`raidteam.py`, once team A).
- Team Potential: the same copies, each at level 50 by its IVs (`raidteam.py`, once team B; `b50`, `no_team_b` in code).
- More in `.claude/rules/roster.md`.
