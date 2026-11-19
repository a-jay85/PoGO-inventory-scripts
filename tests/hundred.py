#!/usr/bin/env python3
"""Checks skills/dex/dex.py hundred_useful: which forms a new 100% copy would help, on a made-up evolution tree and
★100% page. No phone, no data files.

  python3 tests/hundred.py   must say "all hundred cases right"
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.pop("POGO_PHONE", None)
sys.path[:0] = [os.path.join(ROOT, "skills", "dex"), os.path.join(ROOT, "skills", "shared")]

import dex  # noqa: E402

DEX = {"diglett": 50, "diglett_alolan": 50, "dugtrio": 51, "dugtrio_alolan": 51,
       "meowth": 52, "meowth_galarian": 52, "persian": 53, "perrserker": 863,
       "slowpoke": 79, "slowbro": 80,
       "sneasel": 215, "sneasel_hisuian": 215, "weavile": 461, "sneasler": 903,
       "charcadet": 935, "armarouge": 936, "ceruledge": 937,
       "eevee": 133, "vaporeon": 134, "jolteon": 135, "flareon": 136, "espeon": 196,
       "pidgey": 16, "pidgeotto": 17, "pidgeot": 18,
       "mime_jr": 439, "mr_mime": 122, "mr_mime_galarian": 122, "mr_rime": 866,
       "magnemite": 81, "magneton": 82, "magnezone": 462}
PARENT = {"dugtrio": "diglett", "dugtrio_alolan": "diglett_alolan", "persian": "meowth",
          "perrserker": "meowth_galarian", "slowbro": "slowpoke", "weavile": "sneasel",
          "sneasler": "sneasel_hisuian", "armarouge": "charcadet", "ceruledge": "charcadet",
          "vaporeon": "eevee", "jolteon": "eevee", "flareon": "eevee", "espeon": "eevee",
          "pidgeotto": "pidgey", "pidgeot": "pidgeotto", "mr_mime": "mime_jr",
          "mr_mime_galarian": "mime_jr", "mr_rime": "mr_mime_galarian",
          "magneton": "magnemite", "magnezone": "magneton"}
BY = {s: {"dex": d} for s, d in DEX.items()}

# (what, missing numbers, owned 100s, forms that must be wanted, forms that must not)
CASES = [
    ("two plain Diglett fill 50 and 51: no Alolan one", {50, 51}, {"diglett": 2}, set(),
     {"diglett", "diglett_alolan", "dugtrio", "dugtrio_alolan"}),
    ("one Diglett fills 50 and 51 by evolving", {50, 51}, {"diglett": 1}, set(),
     {"diglett", "diglett_alolan", "dugtrio", "dugtrio_alolan"}),
    ("no Diglett owned: either form is wanted", {50, 51}, {},
     {"diglett", "diglett_alolan", "dugtrio", "dugtrio_alolan"}, set()),
    ("only a Galarian Meowth reaches Perrserker", {863}, {"meowth": 3}, {"meowth_galarian", "perrserker"},
     {"meowth", "persian"}),
    ("no Slowpoke owned: still wanted", {79, 80}, {}, {"slowpoke", "slowbro"}, set()),
    ("only a Hisuian Sneasel reaches Sneasler", {903}, {"sneasel": 2}, {"sneasel_hisuian", "sneasler"},
     {"sneasel", "weavile"}),
    ("one Charcadet fills one branch: a second is wanted", {935, 936, 937}, {"charcadet": 1},
     {"charcadet", "armarouge", "ceruledge"}, set()),
    ("two Charcadet fill both branches", {935, 936, 937}, {"charcadet": 2}, set(),
     {"charcadet", "armarouge", "ceruledge"}),
    ("four Eevee fill four Eeveelutions", {134, 135, 136, 196}, {"eevee": 4}, set(), {"eevee", "espeon"}),
    ("three Eevee: one more is wanted", {134, 135, 136, 196}, {"eevee": 3}, {"eevee", "vaporeon"}, set()),
    ("Pidgeot on the page fills Pidgey's hole", {16, 17}, {}, set(), {"pidgey", "pidgeotto", "pidgeot"}),
    ("one Mime Jr fills 439, 122 and 866", {439, 122, 866}, {"mime_jr": 1}, set(),
     {"mime_jr", "mr_mime", "mr_mime_galarian", "mr_rime"}),
    ("a plain Mr. Mime can't reach Mr. Rime", {866}, {"mr_mime": 2}, {"mime_jr", "mr_mime_galarian"},
     {"mr_mime"}),
    ("no Magnemite owned: wanted", {81, 82, 462}, {}, {"magnemite"}, set()),
    ("one Magnemite owned: not wanted", {81, 82, 462}, {"magnemite": 1}, set(),
     {"magnemite", "magneton", "magnezone"}),
]

bad = 0
for what, missing, owned, want, nope in CASES:
    got = dex.hundred_useful(missing, owned, BY, PARENT)
    miss, extra = want - got, nope & got
    if miss or extra:
        bad += 1
        print(f"WRONG {what}: not wanted {sorted(miss)}, wanted {sorted(extra)}")
if bad:
    sys.exit(f"{bad} of {len(CASES)} hundred cases wrong")
print(f"all {len(CASES)} hundred cases right")
