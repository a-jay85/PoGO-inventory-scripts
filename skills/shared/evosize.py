#!/usr/bin/env python3
"""A Pokémon's height and weight after it evolves, and whether that sets a sure Pokédex size record.

  python3 evosize.py <species> <into> <kg> <m>     -> its height and weight range as <into>
  python3 evosize.py test                          -> run the examples

The math (brandonenright.net/pogo_size.html, from catch data; .claude/rules/dex.md): evolving keeps the size class and
both hidden size numbers. h = height / species average height stays the same, so height = the new species' average
height x h. Weight = species average weight x (w + h² - 1), with w hidden, so it scales by the two species' average
weights too. Only XXL can be stretched to a new family top (Eevee 1.75 -> Vaporeon 1.55): this file is for the small
sizes (xxs to xl), where h never changes.

The page shows kg and m with 2 decimals, so the true values sit 0.005 either side. Weight gets WEIGHT_SLACK more on
each side: Enright's Noibat -> Noivern test came out 0.3% off the real one, and his range was +-0.6%.
A record is sure only when the whole range beats the record box's value by more than its rounding.
"""
import os, sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import pvp

ROUND = 0.005  # the page's 2 decimals
WEIGHT_SLACK = 0.02  # each side of the weight, as a share of it: more than Enright's +-0.6%, to be sure


def average(sid):
    """(average height m, average weight kg) of a species, or None if the game data has no size for it"""
    s = (pvp.SPECIES.get(sid) or pvp.SPECIES.get(sid.removesuffix("_SHADOW")) or {}).get("size") or {}
    return (s["h"], s["w"]) if s.get("h") and s.get("w") else None


def after(sid, into, kg, m):
    """the size of a (not XXL) sid of kg and m once it's into. -> (m_lo, m_hi, kg_lo, kg_hi) or None (no size data)"""
    a, b = average(sid), average(into)
    if not a or not b:
        return None
    rh, rw = b[0] / a[0], b[1] / a[1]
    return ((m - ROUND) * rh, (m + ROUND) * rh,
            (kg - ROUND) * rw * (1 - WEIGHT_SLACK), (kg + ROUND) * rw * (1 + WEIGHT_SLACK))


def sure_small(size, record):
    """size: after()'s range. record: a dex_records row (kg_min, m_min). -> the records it surely beats on the small
    side: ['shortest', 'lightest']. A row with no box (all None: none caught yet) is beaten by anything"""
    m_lo, m_hi, kg_lo, kg_hi = size
    if all(record.get(k) is None for k in ("kg_min", "kg_max", "m_min", "m_max")):
        return ["first record"]
    out = []
    if record.get("m_min") is not None and m_hi < record["m_min"] - ROUND:
        out.append("shortest")
    if record.get("kg_min") is not None and kg_hi < record["kg_min"] - ROUND:
        out.append("lightest")
    return out


def holds_small(kg, m, record):
    """this one, as it is, is (or ties) the record holder on the small side -> ['shortest', 'lightest']"""
    out = []
    if record.get("m_min") is not None and m <= record["m_min"]:
        out.append("shortest")
    if record.get("kg_min") is not None and kg <= record["kg_min"]:
        out.append("lightest")
    return out


def test():
    bad = 0

    def check(what, got, want):
        nonlocal bad
        ok = got == want
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {what}: {got}" + ("" if ok else f" (want {want})"))

    # Bulbasaur 0.7 m 6.9 kg -> Ivysaur 1.0 m 13.0 kg
    s = after("BULBASAUR_NORMAL", "IVYSAUR_NORMAL", 3.45, 0.35)
    check("height exact", (round(s[0], 3), round(s[1], 3)), (0.493, 0.507))
    check("weight scales", round((s[2] + s[3]) / 2, 2), 6.5)
    check("beats a far record", sure_small(s, {"kg_min": 7.0, "m_min": 0.6}), ["shortest", "lightest"])
    check("too close to call", sure_small(s, {"kg_min": 6.6, "m_min": 0.51}), [])
    check("tie is no record", sure_small(s, {"kg_min": 1.0, "m_min": 0.507}), [])
    check("no box yet", sure_small(s, {"kg_min": None, "kg_max": None, "m_min": None, "m_max": None}), ["first record"])
    check("holds", holds_small(3.45, 0.35, {"kg_min": 3.45, "m_min": 0.3}), ["lightest"])
    check("shadow uses plain sizes", after("BULBASAUR_NORMAL_SHADOW", "IVYSAUR_NORMAL_SHADOW", 3.45, 0.35) == s, True)
    print("all evosize cases right" if not bad else f"{bad} wrong")
    return bad


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["test"]:
        sys.exit(test())
    if len(a) != 4:
        sys.exit(__doc__)
    got = after(a[0], a[1], float(a[2]), float(a[3]))
    print("no size data" if not got else f"{got[0]:.2f}-{got[1]:.2f} m, {got[2]:.2f}-{got[3]:.2f} kg")
