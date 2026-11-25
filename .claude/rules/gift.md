---
paths:
  - "skills/gift/**"
---
# /gift notes (the rules themselves are in gift.py's top comment)

- A wrong send costs the user's trust. It's why auto-transfer isn't allowed. Never loosen the guards: never Chicago/Raleigh/North Carolina, never a title or city the account doesn't send, and the preview must match before SEND. Cards swap places and stale cards show, so never trust list position alone.
- Open the friendship screen only when a friend may really be 1-2 points away. The user dislikes needless checks. HashTagAJay never opens it (NO_LEVELUP, 2026-11-21: that account needs no more XP). CyrillJan still does.
- Fast gift-list scrolls are fine: it only needs one eligible gift. Don't shrink the scroll to see every card.
- A grey SEND GIFT doesn't mean an empty bag. The only proven empty-bag sign is the picker having none of ours.
- A count with no rows is a game bug: add a space to the search, don't retype.
- The friend list's header shows before its rows (16 s seen on the iPhone), so search() waits for rows. An empty list in swap_zone can be real, so no wait there.
- A Remote Trade friend stays on top whatever the sort; on the iPhone their row shows a countdown. Their arrow doesn't end a search.
- Friends can move from iii to lll mid-day. That's expected.
- A finished iii zone is skipped until midnight (`~/.config/pogo/gift_iii_<trainer>.json`, delete to reset). `iii + rest` is always searched: a friend added today lands there. Once `iii + rest` or `lll + rest` finishes clean, later runs that day skip that search's zones and go straight to its rest (the user, 2026-11-24: saves ~2 min a run).
- Gift runs use CyrillJan on the Pixel. CyrillJan sends San Francisco only (Claude's call; the user can widen it). The user may later give a list of local gift names to replace the city rule.
- OCR can read one line across two cards in a row. Such a card waits for a clean read. SF titles may hold a comma.
- The user sends gifts very fast by hand and wants the script to match. Speed-test with `gift.py --dry-run --walk` and read steps.txt for gaps. Each empty-search nudge costs about 13 s.
- An adb exit 255 on the first look after a PIN unlock: cause unproven. If it comes back, read the stderr.
- Not yet seen live: a non-SF California send, the CPD skip, a real take-over, the Android trade-countdown row, the new heart tap on the iPhone, the gift list/preview/SEND at the new timings (check the first log for "didn't open it", "preview reads").
