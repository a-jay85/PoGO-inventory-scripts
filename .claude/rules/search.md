---
paths:
  - "skills/shared/search.py"
  - "skills/shared/SEARCH.md"
  - "skills/shared/tagsheet.py"
  - "skills/shared/savedsearch.py"
---
# Search notes

- New search code goes through `start_search`, or calls `nudge_bar` on 0 results. A real 0 costs about 2-3 s more on Pokémon searches and 5-10 s on friend searches. A count that grows after a nudge is a bug.
- On the Pixel, `nudge_bar` doesn't check that its A landed. A typed search that fills the bar can lose its end to the delete.
- The iPhone `bar_ready` A can land late, in front of the query (`Apikachu`). `stray_a` catches only that one case.
- Fixed 2026-11-18: `6&!shadow6&!shadow` in the bar. On the Pixel the magnifier read as its own 'a' box in front of `6&!shadow`, so `ui.search_box` saw two boxes and the bar read empty, and the retype doubled it. `search_box` now drops that 'a', and a `type_into_panel` retry reads the bar first (`late_keys`). The old ivc stop `888&!shadow888&!shadow` was likely the same.
- Never seen live: both trade nudges (the friend box, the picker `reopen`), the 0 branch of `run_shortcut`, trade's `blank_list`. Look for "an A and a delete" in run logs.
