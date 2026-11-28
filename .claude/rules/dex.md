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
- MY RECORDS counts evolved Pokémon (the user, 2026-11-27). So evolving a spare can set a record on its own account. Why CyrillJan's Milotic, Huntail, Gorebyss, Ludicolo and Beautifly had no box on 2026-11-12 isn't known.
- A trade updates the receiver's record: trade runs on 2026-11-12 and 2026-11-14 got "New Height Record" cards.
- Size after evolving (brandonenright.net/pogo_size.html, from catch data): the size class and both hidden size numbers stay. Height = new species average height × the same ratio (an XXL in a family whose XXL top changes, like Eevee 1.75 → Vaporeon 1.55, is stretched to the new top instead). Weight = new species average weight × (w + h² − 1), or (w + h − 1) for XXL, where h = height ÷ species average and w is a hidden number near 1. Weight can only be predicted to about ±1 kg on a 116 kg Noivern. The species averages are in PokeMiners' game master (pokemonSettings pokedexHeightM, pokedexWeightKg).
- The user hasn't picked print-only vs auto-tagging for /trade. Print-only was built. Ask before building tagging.
- About 4 s a species, about 70 min an account. Not yet seen live: the end-of-Pokédex stop, the CAUGHT-tab re-tap, regions below UNOVA.
- The full `sizes.py` XXL sweep hasn't been run (only 7 CyrillJan XXLs done). The trade saved searches on the phone have no `!xxl`, so the sweep is what keeps XXLs out. A nickname `XXL` proves nothing.
