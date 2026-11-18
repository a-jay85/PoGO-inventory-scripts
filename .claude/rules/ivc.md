---
paths:
  - "skills/ivc/**"
---
# /ivc notes (the rules are in sort.py's top comment)

- The keep rules are the user's answers. Don't ask again. The weak-line rule is "by feel", using DialgaDex as a guide, and isn't perfected yet. It exists to stop hoarding useless high IVs while staying future-proof. XXL Pumpkaboo/Gourgeist are kept for a future showcase check that isn't built.
- Each Pokémon is opened once per run. New checks go in the LOOK/act path, never a separate step. Act finds a LOOK one on `#IVC&!xxl&!xxs&<dex>`, never the family list, because a nicknamed twin got opened there.
- Something unknown resets the Pixel's list sort. `to_top` never sets it, so `read_results(iv_only)` sorts by Name itself.
- Don't add `xxs` to the `#IVC&xxl,costume` first search. CyrillJan keeps 34 xxs in #IVC for good.
- Speed ideas left out on purpose: skipping pool searches for 98%+ sure keeps (hides fall-outs); `&lucky` only when needed (measured, not worth it); skipping a DOOR whose saved tags look unsure (saved tags can be stale).
- Open bug: `set_tags` never re-checks name+CP before or after ticking, so a tag can land on the wrong Pokémon unseen (seen with Mewtwo).
- Still open: names that are no species, and multi-form names (Vulpix) that guess the first form.
