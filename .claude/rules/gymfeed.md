---
paths:
  - "skills/gymfeed/**"
---
# /gymfeed notes (the rules are in gymfeed.py's top comment)

- Full hearts get fed anyway (badge points). Gold badges are skipped on purpose. Never Golden Razz, Silver Pinap or Poffins.
- The number beside the floating berry is berries fed since the Pokémon went into the gym, not the bag count. Bag counts come from the BERRIES menu only.
- A gold badge needs no meter AND a gold frame: a blend pixel once read silver as gold. The list-ends-at-first-badge-without-bubble rule was measured only on the iPhone.
- A "full" call with a berry still showing means the reader failed. Check the full-*.png shots first when a run feeds too little. A count can't rise after a tap.
- Each defender takes 10 berries per 30 min from its first feed. If a berry is gone, wait 30 min from the first feed before calling it a bug.
- Trust the user's phone sightings over a log. Check the saved full-*.png: the page name must match.
- No swipes between gym Pokémon pages (backlog #14): they never moved to another one on their own, and one left the page and stopped the run. A hidden one is found by taps around the hearts (body_scan). A back-row one often shows only its face, right under its heart. Never short swipes at y .72 on a page (they feed by accident).
- A heart with no motivation left is dark grey, and hearts() misses it. So a gym always counts as 6 until the body scan gives up.
- Floating "+10 STARDUST", "PIPLUP CANDY" or the gym badge (with BADGE PROGRESS) can hide the page name (hence steady_look, badge_over).
- The old gymfeed launchd job and shell scripts in ~/claude-plans/_scripts are retired. Don't move or revive them.
- Not yet seen: all 6 × 10 in 30 min, the Pixel badge reads.
