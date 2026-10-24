---
name: trade
description: Local trades between the user's two Pokémon GO accounts, HashTagAJay (iPhone, through iPhone Mirroring) and CyrillJan (Android phone over adb), far-apart catches first for the most candy. Never makes a special trade. Use when the user says /trade or asks to trade between their accounts.
model: claude-sonnet-5-5
---

# /trade — local trades between the two accounts

Uses the shared tapper and screen reader from /pvpc (`~/.claude/skills/pvpc`: `ui.py`, `run.py`).
`S=~/.claude/skills/trade`.

`caffeinate -dimsu python3 $S/trade.py [--limit N] [--done N]`

Runs on its own. Keep both phones on, both games open, and keep your hands off the Mac mouse while it runs: the iPhone's taps go through the Mac pointer.

- `--limit N`: at most N trades this run (default 48). Two runs come to 96, still under the 99 a day. One run leaves trades free for other friends.
- `--done N`: sets today's count, for trades made by hand before the run.
- `python3 $S/trade.py look`: what screen each phone is on, and its text.
- `python3 $S/trade.py restart`: force-closes Pokémon GO on both phones, opens it again and waits for it to load.

## What one trade does

Before the first trade, each phone opens Pokémon GO if it isn't open, and waits for it to load (`home.py`, see /pvpc).

1. Gets each phone to the other account's friend page: map → profile picture → FRIENDS → search the name → its row → X on a gift → the friend page. Old dialogs (trade expired, cancel this trade, exit Pokémon GO) are cleared on the way. A screen it doesn't know gets Back (Android) or a reopen of the game (iPhone).
2. LOCAL TRADE on both.
3. Reads both saved searches on both phones: `0-100km` (`giv,xlx&distance0-100&countcandy0-2499`) and `100+km` (`giv,xlx&distance100-&countcandy0-2499`).
   Each account gets the trade's candy for the Pokémon it sends. So each pile only holds species its own account has under 2,500 candy of. A far-apart trade is used only when both sides need the candy.
   The run checks the bar shows exactly these searches. An old favorite without `&countcandy0-2499` stops it: save the new one under the same name on both phones.
4. Pairs iPhone 0-100km with Android 100+km. When either runs out, the other way round. When both ways are empty it stops: no trades inside one pile, and none for a species either side has 2,500+ candy of.
5. Sorts the list Recent, newest first (it reads the little arrow on the sort button), and picks the top one on each phone. On the "Are you sure" warning it taps YES only when every reason is a known one (Max Move levels reset). A new reason stops the run.
6. Checks the confirm screen on both phones:
   - The cost reads 100 in white on a dark blue box. Anything else (more than 100, purple digits, a pale box) is a special trade: it stops without confirming.
   - Both phones read the same distance. Under 100 km, the Android puts its pick back and tries its next one, up to 3 times, then stops.
7. CONFIRM on the Android, then the iPhone. Closes the result screens.

## When the trading service fails

"Trading service temporarily unavailable", "Error fetching trade status", or both phones waiting for each other: the run restarts Pokémon GO on both phones and starts the round over. Closing and opening the game often clears it. After 4 failures in a row it stops. The iPhone reopens the game from the Poké Ball in its dock (third icon).

## The day's count

At most 99 trades a day, so one stays free for a special trade made by hand. The count lives in `$S/.state.json` and starts over at midnight. Trades made by hand aren't seen: pass `--done N` for those.

If the special trades left goes down during a run, it stops.

## Runs

Each run writes `runs/<time>/log.txt`. On a stop it keeps both phones' screens there.
