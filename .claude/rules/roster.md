---
paths:
  - "skills/roster/**"
---
# /roster notes

- Don't trust roster.py's form split by @move. DialgaDex lists only the best moves, so the split found 18 Hero Zacian when the user owns 2. The user's tells:
  - Armored Mewtwo has no Mega Evolve button. For Mewtwo, the gap from the `150` search is the Armored count.
  - Fused Necrozma and Kyurem have a "Separate" button.
  - Zacian/Zamazenta Hero vs Crowned show in the types on the detail page.
  - Shaymin Sky vs Land shows in the fast move.
- /raidteam count (the user, 2026-11-18): per pile (one species search, shadow or not) only its top 6 by CP and its top 6 by IV% from the /ivc names count, ties too. The user puts overall IV% a little over a 15 attack, so there's no walk down the list as a safety net. Hundos come in through their "100" names. pokedb comes first: a tile it knows (nickname, CP, species) isn't opened. On a detail page, a hidden button just under the CP arc's right end opens the next Pokémon in the list (`taps.tap_next`), so wanted tiles in a row need no close between.
