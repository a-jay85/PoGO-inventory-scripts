---
name: gift
description: Send Mission Walk and Mission Creek Park gifts to every friend who can take one, on both accounts (HashTagAJay on the iPhone through iPhone Mirroring, CyrillJan on the Android phone). Friends who haven't played with you today go first, far-ahead time zones first, and friends 1 point from a level-up are skipped and tagged WAIT. Use when the user says /gift or asks to send gifts.
model: claude-sonnet-5-5
---

# /gift: send gifts to friends

Uses the shared tapper and screen reader from /pvpc (`~/.claude/skills/pvpc`: `ui.py`, `run.py`, `home.py`).
`S=~/.claude/skills/gift`.

`caffeinate -dimsu python3 $S/gift.py [--limit N] [--dry-run]`

Both phones run at once, each in its own process. `--phone ios` or `--phone android` runs one. Keep your hands off the Mac mouse while the iPhone runs: its taps go through the Mac pointer.

- `--limit N`: at most N gifts per phone this run.
- `--dry-run`: does everything except tap SEND. A nickname is typed into the box, then CANCEL instead of OK. It still taps the phone.
- `python3 $S/gift.py --phone ios look`: what the script reads on the screen now. Taps nothing.

## Which gifts

Only gifts titled exactly **Mission Walk** or **Mission Creek Park**, with no sticker. The gift preview must read the same title before SEND. Every other gift is left for sending by hand. When a phone has neither one left, it stops. The iPhone also quits iPhone Mirroring. The other phone keeps going.

## Who goes first

The friend list is sorted **Can receive a gift**, arrow down. Friends who can take a gift come first, so the first row with the grey arrow badge on the avatar (a gift already sent) ends a search.

1. `iii`: no gift from me and haven't played with me today (`!?&!$&!WAIT&!OPEN&interactable&!EGG&`).
2. `lll`: opened my gift or played with me today (`!WAIT&!OPEN&!interactable&!EGG&`).

Inside each, the time zones farthest ahead go first. They are the user's iPhone text replacements: `lasia`, `leuro`, `latam`, then `ea`, `ce`, `mo`, then the search alone for everyone else.

The iPhone types the shortcuts (`iii`, `lasia` ...) and lets iOS expand them. If the search box still shows a shortcut, it types every search out in full for the rest of the run. Android always types them out in full.

## Friends close to a level-up

Before each gift the script opens the friendship screen (the hearts on the friend page). When the next level is the 3rd, 4th or 5th heart, it taps that heart to read "Earn N more friendship points". The Forever Friends bar shows its number without a tap.

- 1 point to go: no gift. Nickname becomes `WAIT <old nickname>`.
- 2 points to go: gift, then nickname `SENT <old nickname>`.
- An old `WAIT` or `SENT` in front is replaced, not stacked.
- Nicknames hold 12 characters. Too long: the space goes first, then letters off the end (`WAITSouthKor`).
- A nickname the script can't type or read back cleanly is left alone, and the log says to tag it by hand.

iPhone Mirroring sometimes freezes for a few seconds. On the iPhone the script waits 15 seconds for the gift preview and about 20 seconds or more after SEND before it stops. It never taps SEND twice.

## Runs

Each phone writes `runs/<time>-<phone>/log.txt`. On a stop it keeps the phone's screen there.
