#!/usr/bin/env python3
"""PvP stat-product rank helper.

  pvp.py match <species> <cp> <hp> [stars]   -> IV/level combos that give that CP and HP
  pvp.py rank <species> <atk> <def> <hp>      -> ranks in LC/GL/UL for species and its evolutions
"""
import json, math, re, sys, os
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
GM = json.load(open(os.path.join(HERE, "gamemaster.json")))
SPECIES = {p["speciesId"]: p for p in GM["pokemon"]}
CPMS = [float(x) for x in re.search(r"var cpms = \[([^\]]*)\]", open(os.path.join(HERE, "Pokemon.js")).read()).group(1).split(",")]
MAX_LEVEL = 50
LEVELS = [1 + i * 0.5 for i in range(int((MAX_LEVEL - 1) * 2) + 1)]
LEAGUES = [("L", 500), ("G", 1500), ("U", 2500)]
STAR_RANGES = {0: (0, 22), 1: (23, 29), 2: (30, 36), 3: (37, 44), 4: (45, 45)}


def cpm(level):
    return CPMS[int((level - 1) * 2)]


def cp(base, ivs, level):
    a, d, h = (base["atk"] + ivs[0], base["def"] + ivs[1], base["hp"] + ivs[2])
    m = cpm(level)
    return max(10, math.floor(a * math.sqrt(d) * math.sqrt(h) * m * m / 10))


def hp(base, ivs, level):
    return max(10, math.floor((base["hp"] + ivs[2]) * cpm(level)))


def stat_product(base, ivs, cap):
    best = None
    for lv in LEVELS:
        if cp(base, ivs, lv) <= cap:
            best = lv
        else:
            break
    if best is None:
        return 0, None
    m = cpm(best)
    sp = (base["atk"] + ivs[0]) * m * (base["def"] + ivs[1]) * m * hp(base, ivs, best)
    return sp, best


@lru_cache(None)
def table(species, cap):
    base = SPECIES[species]["baseStats"]
    rows = []
    for a in range(16):
        for d in range(16):
            for h in range(16):
                sp, lv = stat_product(base, (a, d, h), cap)
                rows.append((sp, (a, d, h), lv))
    rows.sort(key=lambda r: -r[0])
    return rows


def rank(species, ivs, cap):
    rows = table(species, cap)
    sp = next(r for r in rows if r[1] == ivs)[0]
    # ties share the better rank
    return 1 + sum(1 for r in rows if r[0] > sp + 1e-9)


def family_below_and_self(species):
    """species plus every evolution reachable from it, with depth (0 = itself)."""
    out, stack = [], [(species, 0)]
    while stack:
        s, depth = stack.pop()
        out.append((s, depth))
        for e in SPECIES[s].get("family", {}).get("evolutions", []):
            if e in SPECIES:
                stack.append((e, depth + 1))
    return out


def lc_eligible(species):
    fam = SPECIES[species].get("family", {})
    return "parent" not in fam and bool(fam.get("evolutions"))


def cmd_match(species, cpv, hpv, stars=None):
    base = SPECIES[species]["baseStats"]
    lo, hi = STAR_RANGES[stars] if stars is not None else (0, 45)
    for lv in LEVELS:
        for a in range(16):
            for d in range(16):
                for h in range(16):
                    if lo <= a + d + h <= hi and cp(base, (a, d, h), lv) == cpv and hp(base, (a, d, h), lv) == hpv:
                        print(f"L{lv:<5} {a:>2}/{d:>2}/{h:>2}")


def cmd_rank(species, ivs):
    for s, depth in sorted(family_below_and_self(species), key=lambda x: x[1]):
        parts = []
        for tag, cap in LEAGUES:
            if tag == "L" and not (s == species and lc_eligible(s)):
                continue
            r = rank(s, ivs, cap)
            sp, lv = next((row[0], row[2]) for row in table(s, cap) if row[1] == ivs)
            parts.append(f"{tag}{r} (lv{lv})")
        print(f"{'  ' * depth}{s}: " + ", ".join(parts))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[0] == "match":
        cmd_match(args[1], int(args[2]), int(args[3]), int(args[4]) if len(args) > 4 else None)
    elif args[0] == "rank":
        cmd_rank(args[1], tuple(int(x) for x in args[2:5]))


def best_ranks(species, ivs):
    """{league: (rank, form, depth)} using the best form per league."""
    out = {}
    for s, depth in family_below_and_self(species):
        for tag, cap in LEAGUES:
            if tag == "L" and not (s == species and lc_eligible(s)):
                continue
            r = rank(s, ivs, cap)
            if tag not in out or r < out[tag][0]:
                out[tag] = (r, s, depth)
    return out


def check(species, cpv, hpv, stars):
    base = SPECIES[species]["baseStats"]
    lo, hi = STAR_RANGES[stars]
    for lv in LEVELS:
        for a in range(16):
            for d in range(16):
                for h in range(16):
                    if lo <= a + d + h <= hi and cp(base, (a, d, h), lv) == cpv and hp(base, (a, d, h), lv) == hpv:
                        br = best_ranks(species, (a, d, h))
                        txt = " ".join(f"{t}{r}({s})" for t, (r, s, _) in br.items())
                        flag = "  <== TOP100" if any(r <= 100 for r, _, _ in br.values()) else ""
                        print(f"L{lv:<5} {a:>2}/{d:>2}/{h:>2}  {txt}{flag}")

if __name__ == "__main__" and sys.argv[1] == "check":
    check(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
