#!/usr/bin/env python3
"""Checks the bulk taggers against verdict.py, the one rule book: whatever a tag search would tag must get that same tag
from final_tag. No phone: a small copy of the game's search runs over made-up Pokémon. The species lists are made up too.

  python3 tests/taggers.py

It runs tradeable.py tag's and cleantrades.py's searches in their order, over the saved searches as the phone has them
(CLEAN_TRADES, TRADEABLE below, read 2026-11-04; check them with skills/cleanup/savedsearches.py). A term this file
doesn't know stops it.
"""
import datetime, itertools, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.pop("POGO_PHONE", None)
sys.path.append(os.path.join(ROOT, "skills", "shared"))

import verdict as v  # noqa: E402
from verdict import Facts, GIVER, TAKER  # noqa: E402
import pvp  # noqa: E402
import rules  # noqa: E402
import tradeable as tr  # noqa: E402
from ivc import GYM_DEFENDERS  # noqa: E402

TODAY = datetime.date(2026, 11, 4)
CLEAN_TRADES = {GIVER: "!4*&!3*&traded&!favorite&!#", TAKER: "traded&!3*&!4*&!lucky&!favorite&!xxl&!#"}
TRADEABLE = "!traded&!4*&!3*&!favorite&!xxl&!shiny&!shadow&!legendary&!ultra beasts&!#"

TABLES = {  # made up
    TAKER: {"to": TAKER, "why": {"machop": ("Luckydex", "hole"), "nidoran_female": ("Luckydex", "hole"),
                                 "rhyhorn": ("Reroll", "#1"), "geodude": ("GIV", "PvP"), "magikarp": ("GIV", "hole")},
            "lucky": {"nidoran_female": "female"}, "evolved": {"golem": "stage 2"}, "no_dmax": set(), "xl_full": set(),
            "giv_for_taker": {"tandemaus"}, "raid": {"rhyhorn", "rhydon"}, "raid_self": {"rhydon"}},
    GIVER: {"to": GIVER, "why": {"rhyhorn": ("GIV", "top 6")}, "lucky": {}, "evolved": {"golem": "stage 2"},
            "no_dmax": {"wooloo"}, "xl_full": set(), "giv_for_taker": {"tandemaus"}, "raid": {"rhyhorn", "rhydon"},
            "raid_self": {"rhydon"}},
}
PLAN = {"tags": {"Luckydex": ["&66", "&29&female"], "Reroll": ["&111"], "GIV": ["&74,129"]}, "2xl": ["&111-112"],
        "giv_evolved": ["&76,924", rules.DYNAMAX]}  # tradeable.build_plan's answer for TABLES[TAKER]
SIDS = ["pidgey", "machop", "nidoran_female", "rhyhorn", "rhydon", "geodude", "magikarp", "golem", "tandemaus", "blissey",
        "haunter", "mewtwo", "meltan", "mew", "nihilego", "wooloo"]
FLAGS = ["lucky", "shiny", "shadow", "costume", "background", "gigantamax", "dynamax"]
DATES = [datetime.date(2019, 6, 1), datetime.date(2025, 6, 1), datetime.date(2026, 10, 1)]


def term(t, f, tags=()):
    """does this Pokémon fit one search term?"""
    if t.startswith("!"):
        return not term(t[1:], f, tags)
    kinds = set(pvp.SPECIES[f.sids[0]].get("tags") or [])
    days = (TODAY - f.caught).days

    def within(x, val):
        a, _, b = x.partition("-")
        return int(a) <= val and (not b or val <= int(b)) if "-" in x else val == int(x)

    if t == "#":
        return bool(tags)
    if t.startswith("#"):
        return t[1:] in tags
    if t in ("3*", "4*"):
        return f.iv_sum == 45 if t == "4*" else 37 <= f.iv_sum < 45
    if t == "traded":
        return f.traded
    if t == "favorite":
        return False  # (a search for these only sees ones without a star: the test starts them all so)
    if t in FLAGS:
        return getattr(f, t)
    if t in ("xxl", "xxs", "xs", "xl"):
        return f.size == t
    if t in ("male", "female"):
        return f.gender == t
    if t in ("legendary", "mythical", "ultrabeast"):
        return t in kinds
    if t == "ultra beasts":
        return "ultrabeast" in kinds
    if m := re.fullmatch(r"(year|age|distance|countcandyxl)([\d-]+)", t):
        val = {"year": f.caught.year, "age": days, "distance": 500 if f.far else 5, "countcandyxl": f.candy_xl}[m[1]]
        return within(m[2], val)
    if re.fullmatch(r"\d+(-\d+)?", t):
        return within(t, pvp.SPECIES[f.sids[0]]["dex"])
    raise SystemExit(f"tests/taggers.py doesn't know the search term {t!r}")


def fits(search, f, tags=()):
    """the game's rule: , binds tighter than &"""
    return all(any(term(t, f, tags) for t in part.split(",")) for part in search.split("&") if part)


def tradeable_bulk(f):
    """cmd_tag's tags, in its order -> the tag this Pokémon gets, or None: it's left for the door"""
    pile = lambda q, tags=(): fits(TRADEABLE + q, f, tags)
    for tag, q, tail in tr.bulk_searches(PLAN):
        if pile(q + tail):
            return tag
    for size in tr.sizes.NAMES:
        if pile(tr.size_search(size)):
            return tr.sizes.IVC
    if pile(tr.BULK_REST) and min(f.levels) >= rules.XLX_FOR[TAKER]:
        return rules.XLX
    if any(pile(tr.BULK_REST + q) for q in PLAN["giv_evolved"]) or pile(tr.BULK_REST + "&!traded&distance100-"):
        return "GIV"
    return None


def clean_bulk(f):
    """cleantrades' steps after the door's ones -> the tag this one gets, or None"""
    pile = fits(CLEAN_TRADES[f.account] + rules.BULK_GUARD, f)
    if pile and f.account == rules.EVO_FOR and fits(rules.TRADE_EVOS, f):
        return rules.EVO
    return rules.TRANSFER if pile else None


def grid():
    """made-up Pokémon: every species, with none, one or two of the odd facts, across the facts the searches look at"""
    for sid, n, size, caught, gender, xl, level, far, iv in itertools.product(
            SIDS, range(1 + len(FLAGS) + len(FLAGS) * (len(FLAGS) - 1) // 2), ("", "xs", "xxs", "xxl"), DATES,
            ("male", "female"), (100, 400), (20, 30), (False, True), (30, 40)):
        on = ([()] + [(x,) for x in FLAGS] + list(itertools.combinations(FLAGS, 2)))[n]
        for traded in (False, True):
            yield Facts(sids=[sid], iv_sum=iv, ivs=(10, 10, 10), traded=traded, caught=caught, gender=gender, size=size,
                        kg=1.0, candy_xl=xl, levels=[level], far=far, gym_top20=None, evolves=True,
                        **{k: True for k in on})


def main():
    missing = [s for s in SIDS if s not in pvp.SPECIES]
    if missing:
        sys.exit(f"not in pvp.SPECIES: {missing}")
    gym = {pvp.SPECIES[s]["dex"] for s in GYM_DEFENDERS}
    bad = []
    if gym != set(rules.GYM_DEX):
        bad.append(f"rules.GYM_DEX {sorted(rules.GYM_DEX)} isn't ivc.GYM_DEFENDERS {sorted(gym)}")
    count = tagged = 0
    for base in grid():
        count += 1
        f = v.replace(base, account=GIVER)
        for name, who, got in (("tradeable", GIVER, tradeable_bulk(f)),
                               ("cleantrades", GIVER, clean_bulk(f)),
                               ("cleantrades", TAKER, clean_bulk(v.replace(base, account=TAKER)))):
            g = v.replace(base, account=who)
            if not got:
                if name == "cleantrades" and fits(CLEAN_TRADES[who], g) and not fits(rules.DOOR_PICK, g) \
                        and g.size != "xxl":
                    bad.append(f"{name} {who}: in the pile, but no step takes it: {g}")
                continue
            tagged += 1
            want = v.final_tag(g, TABLES[v.TO[who]], today=TODAY)
            if want.kind != "tag" or want.tags != (got,) or want.star:
                bad.append(f"{name} {who}: tags {got}, the rule book says {want.kind} {want.tags} ({want.why}): {g}")
    if bad:
        print("\n".join(bad[:25]))
        sys.exit(f"{len(bad)} differences ({count} Pokémon, {tagged} tagged)")
    print(f"all {count} Pokémon: the bulk taggers and the rule book say the same ({tagged} tags)")


if __name__ == "__main__":
    main()
