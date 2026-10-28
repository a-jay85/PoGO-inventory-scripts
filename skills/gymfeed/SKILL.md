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
4. Taps **TIME DEFENDING** to go into the gym. A badge with no TIME DEFENDING means none of yours is in a gym any more: the run ends.
5. Taps each Pokémon in the gym view, right-most first. On its page it taps the floating berry every 2.5 s until the berry goes away. A Pokémon takes up to 10 a day. Then the round X back to the gym view.
6. A Pokémon a tap can't open (one in the back row, behind another) is found by swiping from the ones it did open. Swipes go only part way along a gym, and some only take with the finger held still first, on the spot where the hidden Pokémon shows.
7. Back to the badge list, sorted again, the next badge. It ends after N berries or when no gym is left.

A berry counts when the number under it goes down. Log in `$S/runs/<time>-<phone>/log.txt`.
