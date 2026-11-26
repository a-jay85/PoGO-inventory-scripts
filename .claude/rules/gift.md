---
paths:
  - "skills/gift/**"
---
# /gift notes (the rules themselves are in gift.py's top comment)

- A wrong send costs the user's trust. It's why auto-transfer isn't allowed. Never loosen the guards: never Chicago/Raleigh/North Carolina, never a title or city the account doesn't send, and the preview must match before SEND. Cards swap places and stale cards show, so never trust list position alone.
- Open the friendship screen only when a friend may really be 1-2 points away. The user dislikes needless checks. Both accounts check it and tag WAIT and SENT. On HashTagAJay a WAIT friend still gets a gift (GIFT_WAIT, the user 2026-11-25: that account needs no more XP, but the tags stay so the friend's side can claim it whenever). CyrillJan holds a WAIT friend's gift back.
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
- Opening (from 23:00, `gift.py open` any time): the gift box only shows from the list's tap, never from the friend page after its X, so each open is tap, X, page, back, tap, OPEN. After OPEN the screen is blank ~5 s, then the friend page comes back by itself (iPhone, 2026-11-25). On the Pixel the items fly in first ("+1 | Egg | +200 | Stardust"). CyrillJan's item bag was full on 2026-11-25: its opens stop at once until the user clears it.
- The GIFT sort's picture reads 0.68 on the Can receive a gift picture: sorted_gift() needs the wanted one to beat the other, or a send run after an open pass would think it's sorted right.
- Not yet seen live: the Lucky Friends screen and the level-up screen after OPEN (each is logged as "after OPEN:" with a capture).
- The daily open limit (iPhone, 2026-11-25): after OPEN the box goes straight back to the friend page (no blank, no items) with a pink pill in the middle, like gymfeed's raid message. Nothing gets past it till the day resets, so it ends the open pass, the run's last step. The run that found it logged 3 friends as opened that way. The pill's words aren't known yet: the first stop keeps an `open_limit` capture, so add them to LIMIT_WORDS from it.
- The red GPS banner (location off for most Pixel runs) hides the tabs and counts at the top. Read what it hides with `ui.under_gps_banner` or `ui.banner_tabs` (storage tabs, or `tabs=ui.TRAINER_TABS`). Never guess the screen from other rows instead.
