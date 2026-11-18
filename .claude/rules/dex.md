---
paths:
  - "skills/dex/**"
  - "skills/cleanup/sizes.py"
---
# /dex notes (check dex.py's top comment first)

- Lucky rules (user's): if the account has enough lucky pre-evolutions to fill a whole family's holes, leave the family out. Evolutions GO doesn't have yet (Duraludon → Archaludon) still count. The lucky-source tag search includes maybes (Wurmple, Basculin, too few copies) until the hole is filled. Untradeables (Gimmighoul, Gholdengo) are left out.
- Output format: bare dex numbers with ranges.
- Luckydex safe terms always go at the end: `&!#&!favorite&!traded&!shadow&!shiny&!XXL&!4*&!3*&`.
- XXS stays XXS when it evolves. The XXS page checks Gimmighoul → Gholdengo too.
- ★100%: every rule goes through `dex.hundred_useful`. Open: Pokémon tagged GIV before that fix (Caterpie, Weedle, Pidgey, Gastly, Dratini, Sinnoh starters; 38 dex numbers) may still carry a stale GIV tag.
- When two steps do the same logic, refactor into one copy (user preference).

## sizerecords and XXL
- MY RECORDS seems to count only Pokémon caught as that species (Milotic, Huntail, Gorebyss, Ludicolo, Beautifly have no box on CyrillJan).
- Unknown whether a trade updates the receiver's record: read the receiver's page before and after the first trade.
- The user hasn't picked print-only vs auto-tagging for /trade. Print-only was built. Ask before building tagging.
- About 4 s a species, about 70 min an account. Not yet seen live: the end-of-Pokédex stop, the CAUGHT-tab re-tap, regions below UNOVA.
- The full `sizes.py` XXL sweep hasn't been run (only 7 CyrillJan XXLs done). The trade saved searches on the phone have no `!xxl`, so the sweep is what keeps XXLs out. A nickname `XXL` proves nothing.
