---
paths:
  - "skills/shared/verdict.py"
  - "skills/shared/rules.py"
---
# Rule book notes (the rules are in verdict.py and rules.py)

- Why: never Transfer by default, only when very sure a Pokémon is useless to both accounts. Unsure = leave it as it is and log it to the not-sure list. There is no Review tag. Transfer stays a tag the user reviews before transferring.
- CyrillJan isn't a completionist account (no Luckydex, ★100% or roster for it). It wants good PvE ones and XL-candy droppers. Tandemaus gets Reroll on CyrillJan because HashTagAJay wants the family-of-3 Maushold. On CyrillJan (2026-11-23) Reroll = HashTagAJay needs it, GIV = CyrillJan needs the trade's candy (under 348 Candy, or under 360 XL of a team line: verdict.giver_short). A team line (the user, 2026-11-23): a family with a species on Team Future, Team Ideal, or one of CyrillJan's Team Availables or Potentials (tradeable.team_lines). Other lines don't spend trades on 360 XL.
- Team Future/Ideal XL bar, both accounts (the user, 2026-11-23): a line whose #1 non-mega pick is on Team Future or Team Ideal wants 360 Candy XL for each 100 the account has of it (or of an earlier stage), up to 5. Under it: GIV (verdict.team_short). The 100s come from a `4*` count on the phone (`tradeable.py team100`; specieswise counts first). 2XL and the shadow rule stay at 360.
- Luckies are always traded, so there is no untraded-lucky case.
- Never add an age limit back to saved species lists on either account. An 8-day-old Dynamax count left Pokémon untagged.
- When shadow/costume rules overlap, the first match in the order written is the working assumption. The user never stated an order. Shadow costume ones are judged by hand.
