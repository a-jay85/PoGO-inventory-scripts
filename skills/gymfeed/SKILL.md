---
name: gymfeed
description: Feed berries to the Pokémon in the gyms you're defending, from the profile's gym badge list, until 100 berries are fed or no gym is left. Use when the user says /gymfeed or asks to feed the gym defenders.
model: claude-sonnet-5-5
---

# /gymfeed: feed berries to your gyms

Uses the shared tapper and screen reader from /pvpc (`~/.claude/skills/pvpc`). `S=~/.claude/skills/gymfeed`.

`POGO_PHONE=android caffeinate -dimsu python3 $S/gymfeed.py [--limit N]`

Or through the front door: `POGO_PHONE=android caffeinate -dimsu python3 ~/PoGO-inventory-scripts/pogo.py gymfeed`.

- `POGO_PHONE=android`: the Android phone.
- No `POGO_PHONE`: the iPhone. Keep your hands off the Mac mouse while it runs.

`--limit N`: stop after N berries (default 100).

## What it does

1. Profile (ME tab), down to **GYM BADGES / RECENTLY VISITED**, then **LIST** (the green diamond).
2. Sorts the badges by **Defending** (shield), arrow down. The list opens on Recent each time. A 2nd tap on DEFENDING turns the arrow up, so the script reads the arrow in the sort menu first.
3. Opens the first badge that isn't gold and wasn't done this run. A gold badge has no meter under it. Bronze and silver do.
4. Taps **TIME DEFENDING** to go into the gym. A badge with no TIME DEFENDING means none of yours is in a gym any more: the run ends. A gym with a raid on ("Raid in progress!") is skipped.
5. Taps each Pokémon in the gym view, right-most first, a bit under its CP. If nothing new opens, it taps lower: a back-row Pokémon only shows a little between the ones in front.
6. On a Pokémon's page it opens the berry menu (round button, lower left) and picks a berry (below). Then it taps the floating berry every 1.5 s until the berry goes away. A Pokémon takes about 10 at a time, and about 10 more half an hour later. Then the round X back to the gym view.
7. A Pokémon a tap can't open (one in the back row, behind another) is found by swiping from the ones it did open. Swipes go only part way along a gym, and some only take with the finger held still first, on the spot where the hidden Pokémon shows.
8. Back to the badge list, sorted again, the next badge. It ends after N berries or when no gym is left.

## Berries

It feeds Razz, then Nanab, then Pinap, and always leaves some in the bag:

| Berry | Kept |
|---|---|
| Razz | 1 |
| Nanab | 1 |
| Pinap | 30 |
| Golden Razz | all (never fed) |
| Silver Pinap | all (never fed) |

The page opens on Razz for each Pokémon, so the script picks from the menu every time. The menu shows each kind's count. When a kind is down to what's kept, it picks the next one. When none is left to spare, the run ends. The numbers are in `FEEDABLE` at the top of `gymfeed.py`.

A berry counts when the number under it goes down. On the Pixel that number is small, so it's read from a sharp crop. The berry menu was measured on the Pixel only. Log in `$S/runs/<time>-<phone>/log.txt`.
