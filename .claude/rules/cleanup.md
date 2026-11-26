---
paths:
  - "skills/cleanup/**"
---
# /cleanup notes

- The user wants every script as fast as possible, with no artificial pauses, on both phones. The one exception is the appraisal think() pause, about 1 s.
- When the user says something is slow, screen-record the phone (`adb shell screenrecord`) and profile the script. The user doubts the logs show the pauses. Each screenshot+OCR look costs about 1 s, so the fix is fewer looks.
- Tag sheets are longer than the screen. "Transfer" is on the never-tap list: tick the row's box instead.
- Scripts only tag Transfer. They never transfer by themselves: the user doesn't trust auto-transfer yet (after a wrong gift send).
- Run `cleantrades.py transfer` (the Candy XL power-up check) before a mass transfer. Don't run it to catch up old luckies unless asked.
- Rebuild `rules.COSTLY_LINES` from `tradeable.py refresh`'s giv-evolved file when a new >100-candy evolution comes out.
- Transfer, XLX and PvP door opens can't be replaced by bulk searches: level isn't searchable, and high-attack PvP ones often get kept.
- `savedsearches.py` can't see past the first page of favorites. 0-100km and 100+km are past it, so they aren't in `rules.SAVED`.
- Before a tagging script runs on a phone, tell the user what its first steps touch. They expect cleantrades to act on Clean Trades only.
- Never run on the iPhone yet: multi-select and swipe; the sizes.py sweep on HashTagAJay.

## leftovers / specieswise
- The Leftovers saved search (read off the iPhone; the user can't copy it): `!4*&!3*&!#&!favorite&!shiny&!lucky&!shadow&!legendary&!mythical&!ultrabeasts&!pvp&age0-7&!xxl`. `age0-7` keeps it to the last 8 days of catches: older ones were kept on purpose (the user, 2026-11-26).
- HashTagAJay trades away only what helps another, less developed account. It has 360+ XL for most species.
- Regionals not from San Francisco (`rules.SF_NATIVE` lists the ones that are) and Spinda go on the not-sure list; the user tags them by hand.
- Open: shadows are still skipped in the "#1 vs a boss" check (the user didn't pick). Claude chose "whole line, any IV" for gym-defender lines; the user may want it tighter.
- To re-judge a tag pile, use `pogo.py specieswise GIV|Transfer` first (by species, no opening). Use the per-Pokémon door walk (`leftovers.py again`) only if the user asks.
- CyrillJan's #Reroll after a rule change: `specieswise.py Reroll --as CyrillJan --and <dexes>` first (0-2*, not shadows: by search steps, 2026-11-20: 212 in 7 min), then `leftovers.py again Reroll --as CyrillJan --and <dexes>` walks the rest (3*+, shadows, forms a search can't split).
