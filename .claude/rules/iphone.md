---
paths:
  - "skills/shared/ui.py"
  - "skills/shared/helper.swift"
  - "skills/shared/session.py"
  - "skills/shared/home.py"
  - "skills/shared/search.py"
  - "skills/shared/taps.py"
---
# iPhone (Mirroring) notes

- Tap hold: 70-100 ms through Mirroring turns into a long press ("Manage Favorite Search") 5 times in 10. 20-30 ms worked 0 of 34 with no misses, hence `ui.tap_ms()`. If long presses come back, try 15-25 ms (test: `~/claude-plans/_scripts/tap_hold_test.py <ms>` on a Favorite search shortcut).
- Mirroring drops a tap now and then, whatever the hold. Cause unknown. Retry a tap only after a fresh look shows the same screen and word. Never retry the gift card or SEND. If "tag tick" back-outs show up, read the front app and Mac idle time that `set_tags` logs first.
- Typing: TYPE_SPEED's 20 ms gap between keys is there because search chips ate keys at 1 ms (`mega1` stayed `me`). 0/0/0 loses keys. Search retries (panel not taking keys, bar misread) aren't caused by speed. If keys get lost, check the gap is still 20 ms and whether the game changed its typing UI, then panel focus or OCR. `ui.LOOK_PERIOD` keeps wait loops' look pace, because they count looks.
- Number-only searches sometimes lose their last key (150 shows as 15). Cause unknown. `search.lost_tail` mends it for about 1.5 s more. If number searches get slow, look for "typing the lost end" in the logs.
- Pause when active: the script's own clicks and keys reset HIDIdleTime, so "user active" means input newer than the script's last input.
- Taps sent straight to the Mirroring window (postToPid, NSEvent, SkyLight) are ignored, even with Mirroring in front. Keys and captures do work behind another app. Don't retry this route.
- Opening the game: never go back to a fixed icon spot (icons move, event icons change). Pokémon HOME is also on the phone, so the Spotlight Top Hit must be exactly POKÉMON GO.
- The keyboard sometimes doesn't come up on rename, so the retry taps the field again.
- The "Cannot Trade Recently Caught Pokémon Remotely" box after tag DONE cost about 25 s each time before the fix. Not yet seen live after it: check a /pvpc log with Meltans for "keeps the Remote Trade tag" with no "tap DONE didn't land" before it.
- iPhone OCR reads "!" as ":" in the search bar.
- Open: home.start stops on an iPhone left on a friend page (where /trade leaves it). Two taps missed right after a resume; maybe add a short settle after bring_forward(). Untested: a pause during /trade, pauses over 78 s.
- A call (or the iPhone picked up) mid-run: Mirroring shows "iPhone in Use" and connects again by itself once the iPhone is locked. `ui.ocr` hands that page to `base.wait_for_phone`, so no reader ever sees it (it read as "no berry": gymfeed called Garchomp full, 2026-11-23). Not yet seen live: whether the game is still on the same screen after a call.
