---
paths:
  - "skills/shared/verdict.py"
  - "skills/shared/rules.py"
---
# Rule book notes (the rules are in verdict.py and rules.py)

## What each tag means in each storage

A tag means something different in each account's storage. Each storage's pile is judged for the other account (verdict.tables(to), verdict.TO). The code names don't say which storage: `GIVER` is CyrillJan and `TAKER` is HashTagAJay (rules.py), but `giver_species` judges HashTagAJay's storage and `giver_short` judges CyrillJan's.

| | HashTagAJay's storage (Leftovers) | CyrillJan's storage (Tradeable) |
|---|---|---|
| Goes to | CyrillJan (or the user's wife's account) | HashTagAJay |
| Species rules | `tradeable.giver_species` (`to == GIVER` in verdict.py) | `tradeable.taker_species` (`to == TAKER`) |
| Reroll | CyrillJan wants a new 100: a strong line, a raid top vs a 4★+ boss while the line could still make a CyrillJan Team Potential (`no_team_b`), PvPoke's ML top, or a CyrillJan Team Potential line (`giver_team`). A line in only as a Mega: only till CyrillJan has a 100 (`giver_100`) | HashTagAJay needs a new 100 (the user, 2026-11-20 and 2026-11-23): a strong line, a new copy in HashTagAJay's own top 6 vs some boss, a ★100% hole, a PvP pick, a lucky family under 348 Candy, or `rules.REROLL_FOR_TAKER`. A spot won only as a Mega counts for nothing. A family HashTagAJay holds `REROLL_ENOUGH` (5) 100s of gets none. A line HashTagAJay needs 100s of belongs here, never in GIV (the user, 2026-11-25). The one exception: a pattern collection (`sort.COLLECT`) is GIV |
| GIV | The trade is worth making for a reason other than IVs: a medal weight, a 10/12 km egg's family, Smeargle, a gym defender's line (`hard`), a stage 2 or hard stage 1 (`evolved`), a free trade evolution (`EVO_FOR` is CyrillJan), Dynamax, caught 100 km+ away, short for Dynamax, or HashTagAJay short of a Team Future/Ideal XL bar (`team_short`: the trade pays the sender a Candy XL) | CyrillJan needs the trade's candy (the user, 2026-11-23): under 348 Candy, or under 360 Candy XL of a team line (`verdict.giver_short`, which runs `team_short` too). Also a stage 2 or hard stage 1 (`evolved`), Dynamax, caught 100 km+ away, or short for Dynamax |
| Luckydex | (none) | HashTagAJay's Luckydex is missing it (one gender, when the list says so) |
| Transfer | Traded already, or no rule wants it. The user reviews it before transferring | The same |

- Why: never Transfer by default, only when very sure a Pokémon is useless to both accounts. Unsure = leave it as it is and log it to the not-sure list. There is no Review tag. Transfer stays a tag the user reviews before transferring.
- CyrillJan isn't a completionist account (no Luckydex, ★100% or roster for it). It wants good PvE ones and XL-candy droppers. Tandemaus gets Reroll on CyrillJan because HashTagAJay wants the family-of-3 Maushold. A team line (the user, 2026-11-23): a family with a species on Team Future, Team Ideal, or one of CyrillJan's Team Availables or Potentials (tradeable.team_lines). Other lines don't spend trades on 360 XL.
- Team Future/Ideal XL bar, both accounts (the user, 2026-11-23): a line whose #1 non-mega pick is on Team Future or Team Ideal wants 360 Candy XL for each 100 the account has of it (or of an earlier stage), up to 5. Under it: GIV (verdict.team_short). The 100s come from a `4*` count on the phone (`tradeable.py team100`; specieswise counts first). 2XL and the shadow rule stay at 360.
- Luckies are always traded, so there is no untraded-lucky case.
- Never add an age limit back to saved species lists on either account. An 8-day-old Dynamax count left Pokémon untagged.
- When shadow/costume rules overlap, the first match in the order written is the working assumption. The user never stated an order. Shadow costume ones are judged by hand.
