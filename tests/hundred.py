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

DEX = {"DIGLETT_NORMAL": 50, "DIGLETT_ALOLA": 50, "DUGTRIO_NORMAL": 51, "DUGTRIO_ALOLA": 51,
       "MEOWTH_NORMAL": 52, "MEOWTH_GALARIAN": 52, "PERSIAN_NORMAL": 53, "PERRSERKER_NORMAL": 863,
       "SLOWPOKE_NORMAL": 79, "SLOWBRO_NORMAL": 80,
       "SNEASEL_NORMAL": 215, "SNEASEL_HISUIAN": 215, "WEAVILE_NORMAL": 461, "SNEASLER_NORMAL": 903,
       "CHARCADET_NORMAL": 935, "ARMAROUGE_NORMAL": 936, "CERULEDGE_NORMAL": 937,
       "EEVEE_NORMAL": 133, "VAPOREON_NORMAL": 134, "JOLTEON_NORMAL": 135, "FLAREON_NORMAL": 136, "ESPEON_NORMAL": 196,
       "PIDGEY_NORMAL": 16, "PIDGEOTTO_NORMAL": 17, "PIDGEOT_NORMAL": 18,
       "MIME_JR_NORMAL": 439, "MR_MIME_NORMAL": 122, "MR_MIME_GALARIAN": 122, "MR_RIME_NORMAL": 866,
       "MAGNEMITE_NORMAL": 81, "MAGNETON_NORMAL": 82, "MAGNEZONE_NORMAL": 462}
PARENT = {"DUGTRIO_NORMAL": "DIGLETT_NORMAL", "DUGTRIO_ALOLA": "DIGLETT_ALOLA", "PERSIAN_NORMAL": "MEOWTH_NORMAL",
          "PERRSERKER_NORMAL": "MEOWTH_GALARIAN", "SLOWBRO_NORMAL": "SLOWPOKE_NORMAL", "WEAVILE_NORMAL": "SNEASEL_NORMAL",
          "SNEASLER_NORMAL": "SNEASEL_HISUIAN", "ARMAROUGE_NORMAL": "CHARCADET_NORMAL", "CERULEDGE_NORMAL": "CHARCADET_NORMAL",
          "VAPOREON_NORMAL": "EEVEE_NORMAL", "JOLTEON_NORMAL": "EEVEE_NORMAL", "FLAREON_NORMAL": "EEVEE_NORMAL", "ESPEON_NORMAL": "EEVEE_NORMAL",
          "PIDGEOTTO_NORMAL": "PIDGEY_NORMAL", "PIDGEOT_NORMAL": "PIDGEOTTO_NORMAL", "MR_MIME_NORMAL": "MIME_JR_NORMAL",
          "MR_MIME_GALARIAN": "MIME_JR_NORMAL", "MR_RIME_NORMAL": "MR_MIME_GALARIAN",
          "MAGNETON_NORMAL": "MAGNEMITE_NORMAL", "MAGNEZONE_NORMAL": "MAGNETON_NORMAL"}
BY = {s: {"dex": d} for s, d in DEX.items()}

# (what, missing numbers, owned 100s, forms that must be wanted, forms that must not)
CASES = [
    ("two plain Diglett fill 50 and 51: no Alolan one", {50, 51}, {"DIGLETT_NORMAL": 2}, set(),
     {"DIGLETT_NORMAL", "DIGLETT_ALOLA", "DUGTRIO_NORMAL", "DUGTRIO_ALOLA"}),
    ("one Diglett fills 50 and 51 by evolving", {50, 51}, {"DIGLETT_NORMAL": 1}, set(),
     {"DIGLETT_NORMAL", "DIGLETT_ALOLA", "DUGTRIO_NORMAL", "DUGTRIO_ALOLA"}),
    ("no Diglett owned: either form is wanted", {50, 51}, {},
     {"DIGLETT_NORMAL", "DIGLETT_ALOLA", "DUGTRIO_NORMAL", "DUGTRIO_ALOLA"}, set()),
    ("only a Galarian Meowth reaches Perrserker", {863}, {"MEOWTH_NORMAL": 3}, {"MEOWTH_GALARIAN", "PERRSERKER_NORMAL"},
     {"MEOWTH_NORMAL", "PERSIAN_NORMAL"}),
    ("no Slowpoke owned: still wanted", {79, 80}, {}, {"SLOWPOKE_NORMAL", "SLOWBRO_NORMAL"}, set()),
    ("only a Hisuian Sneasel reaches Sneasler", {903}, {"SNEASEL_NORMAL": 2}, {"SNEASEL_HISUIAN", "SNEASLER_NORMAL"},
     {"SNEASEL_NORMAL", "WEAVILE_NORMAL"}),
    ("one Charcadet fills one branch: a second is wanted", {935, 936, 937}, {"CHARCADET_NORMAL": 1},
     {"CHARCADET_NORMAL", "ARMAROUGE_NORMAL", "CERULEDGE_NORMAL"}, set()),
    ("two Charcadet fill both branches", {935, 936, 937}, {"CHARCADET_NORMAL": 2}, set(),
     {"CHARCADET_NORMAL", "ARMAROUGE_NORMAL", "CERULEDGE_NORMAL"}),
    ("four Eevee fill four Eeveelutions", {134, 135, 136, 196}, {"EEVEE_NORMAL": 4}, set(), {"EEVEE_NORMAL", "ESPEON_NORMAL"}),
    ("three Eevee: one more is wanted", {134, 135, 136, 196}, {"EEVEE_NORMAL": 3}, {"EEVEE_NORMAL", "VAPOREON_NORMAL"}, set()),
    ("Pidgeot on the page fills Pidgey's hole", {16, 17}, {}, set(), {"PIDGEY_NORMAL", "PIDGEOTTO_NORMAL", "PIDGEOT_NORMAL"}),
    ("one Mime Jr fills 439, 122 and 866", {439, 122, 866}, {"MIME_JR_NORMAL": 1}, set(),
     {"MIME_JR_NORMAL", "MR_MIME_NORMAL", "MR_MIME_GALARIAN", "MR_RIME_NORMAL"}),
    ("a plain Mr. Mime can't reach Mr. Rime", {866}, {"MR_MIME_NORMAL": 2}, {"MIME_JR_NORMAL", "MR_MIME_GALARIAN"},
     {"MR_MIME_NORMAL"}),
    ("no Magnemite owned: wanted", {81, 82, 462}, {}, {"MAGNEMITE_NORMAL"}, set()),
    ("one Magnemite owned: not wanted", {81, 82, 462}, {"MAGNEMITE_NORMAL": 1}, set(),
     {"MAGNEMITE_NORMAL", "MAGNETON_NORMAL", "MAGNEZONE_NORMAL"}),
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
