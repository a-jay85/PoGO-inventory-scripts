---
paths:
  - "skills/shared/door.py"
  - "skills/shared/pagefacts.py"
  - "skills/shared/fallen.py"
  - "skills/cleanup/tradeable.py"
---
# Door and page-fact notes

- A page fact that doesn't read = None = door not sure.
- Costume is still 1 search (user's choice). Other facts come from the page (traded, caught date, far place = not California, Candy XL) and tile icons.
- Background icon = snowflake OR globe, pale blue bluer than green, isolated (ring test). False hits seen: a teal glow behind Baltoy/Bronzor/Jigglypuff, and Wobbuffet's body. Boxes sit on column middles, because bottom-row shinies were missed.
- Gold lucky bubbles on tiles (`pagefacts.tile_icons`): use them only if they never call a non-lucky one lucky. When a list read looks short, check the game's own count before blaming the reader.
- Gym rank: only CyrillJan's Blissey/Chansey are named (their XXL-named ones stay IV-less). Other gym species and HashTagAJay aren't, so the door mostly says not sure for them.
- Only tradeable sets `android.PREFETCH_AGE = 0.8`. The default stays 0.3, because gymfeed read a berry count too early at 0.8.
- Next speed candidates: page_bottom/back_to_top (~9 s a Pokémon) and the tag sheet (~8 s). cost_levels' "no two looks agreed" (7 looks, 5-6 a run) was a lucky one's CP read as 'P2709': fixed 2026-11-18. It keeps one capture a run of a page whose CP still doesn't read. Gains mostly show when the Mac is busy. Test on a refilled Tradeable pile.
- Phone tests stay small: one page of a kind shows the answer. `150` list order moves between runs, so pin a page by age or CP.
- Open: Mewtwo '98ADY' read not-California once (a not-California answer logs the words read, check that line). A Zamazenta page read all None once on the iPhone.
- Not yet seen live: a GuaranteedLucky/Old tag from the fallen walk; the iPhone early stop; `back_to_top`'s left-edge drag.
