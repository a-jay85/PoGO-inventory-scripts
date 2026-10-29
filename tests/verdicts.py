#!/usr/bin/env python3
"""Pins the final tag skills/shared/verdict.py gives each made-up Pokémon. No phone, no data files: the species lists
here are made up too, so only the rules and their order are tested.

  python3 tests/verdicts.py            check every case against tests/verdicts.json
  python3 tests/verdicts.py --record   write verdicts.json from today's code (after a change you meant)
"""
import datetime, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "tests", "verdicts.json")
os.environ.pop("POGO_PHONE", None)
sys.path.append(os.path.join(ROOT, "skills", "shared"))

import verdict as v  # noqa: E402
from verdict import Facts, GIVER, TAKER  # noqa: E402

TODAY = datetime.date(2026, 10, 29)
NEW = datetime.date(2026, 6, 1)  # 150 days: not Old
OLD = datetime.date(2025, 6, 1)  # 515 days: Old
LUCKY = datetime.date(2019, 6, 1)

TABLES = {  # made up
    TAKER: {"to": TAKER, "why": {"machop": ("Luckydex", "lucky dex hole"), "nidoran_female": ("Luckydex", "lucky dex hole"),
                                 "rhyhorn": ("Reroll", "#1 raid attacker"), "geodude": ("GIV", "PvP"),
                                 "magikarp": ("GIV", "★100% hole")},
            "lucky": {"nidoran_female": "female"}, "evolved": {"golem": "stage 2"}, "no_dmax": set(),
            "xl_full": set(), "giv_for_taker": {"tandemaus"}},
    GIVER: {"to": GIVER, "why": {"rhyhorn": ("GIV", "top 6 vs a boss")}, "lucky": {}, "evolved": {"golem": "stage 2"},
            "no_dmax": {"wooloo"}, "xl_full": set(), "giv_for_taker": {"tandemaus"}},
}


def plain(**kw):
    """an untraded, new, ordinary, under-26 Pokémon that fits no rule, with every fact read"""
    d = dict(account=GIVER, sids=["pidgey"], iv_sum=30, traded=False, caught=NEW, gender="male", size="",
             kg=1.0, candy_xl=400, levels=[20], far=False, gym_top20=None)
    d.update(kw)
    return Facts(**d)


CASES = {
    # never Transfer by default: a fact not read -> unsure
    "plain": plain(),
    "no account": plain(account=None),
    "no appraisal": plain(iv_sum=None),
    "98%": plain(iv_sum=44),
    "species not read": plain(sids=None),
    "two species": plain(sids=["pidgey", "rattata"]),
    "two forms": plain(sids=["rattata", "rattata_alolan"]),
    "traded not read": plain(traded=None),
    "catch date not read": plain(caught=None),
    "size not read": plain(size=None),
    "level not read": plain(levels=None),
    "level 25 or 26": plain(levels=[25.5, 26]),
    "distance not checked": plain(far=None),
    "no species lists": (plain(sids=["machop"]), {"to": TAKER, "missing": "no a lucky /dex run for HashTagAJay yet"}),
    # by hand, for now
    "your tag": plain(other_tags=["Evo"]),
    "shadow": plain(shadow=True),
    "lucky": plain(lucky=True),
    "costume": plain(costume=True),
    "background": plain(background=True),
    "shiny": plain(shiny=True),
    "gigantamax": plain(gigantamax=True),
    "mythical": plain(sids=["mew"]),
    # trades.py's legendary rules
    "legendary untraded": plain(sids=["entei"]),
    "legendary untraded old": plain(sids=["entei"], caught=OLD),
    "legendary traded": plain(sids=["entei"], traded=True),
    "legendary fused": plain(sids=["kyurem_black"]),
    "meltan": plain(sids=["meltan"]),
    "ultra beast": plain(sids=["nihilego"]),
    # gym defenders
    "gym not checked": plain(sids=["snorlax"]),
    "gym top 20": plain(sids=["snorlax"], gym_top20=True),
    "gym not top 20": plain(sids=["snorlax"], gym_top20=False),
    "gym top 20 traded": plain(sids=["snorlax"], gym_top20=True, traded=True),
    # the order, CyrillJan's pile (to HashTagAJay)
    "traded": plain(traded=True),
    "traded Machoke: Evo": plain(sids=["machoke"], traded=True),
    "H traded Machoke: Transfer": plain(account=TAKER, sids=["machoke"], traded=True),
    "legendary XXL": plain(sids=["entei"], size="xxl"),
    "legendary size not read": plain(sids=["entei"], size=None),
    "H size not read, under 360 XL": plain(account=TAKER, size=None, candy_xl=120),
    "2019 catch": plain(caught=LUCKY),
    "2019 catch, Luckydex": plain(sids=["machop"], caught=LUCKY),
    "Luckydex": plain(sids=["machop"], caught=OLD),
    "Luckydex wrong gender": plain(sids=["nidoran_female"], gender="male"),
    "Luckydex right gender": plain(sids=["nidoran_female"], gender="female"),
    "Luckydex gender not read": plain(sids=["nidoran_female"], gender=None),
    "Old": plain(caught=OLD),
    "Old beats Reroll": plain(sids=["rhyhorn"], caught=OLD),
    "Reroll": plain(sids=["rhyhorn"]),
    "GIV": plain(sids=["geodude"], levels=[30]),
    "XXL": plain(size="xxl", levels=[30]),
    "xxs": plain(size="xxs"),
    "XLX": plain(levels=[26, 26.5]),
    "XLX beats evolved": plain(sids=["golem"], levels=[27]),
    "evolved": plain(sids=["golem"]),
    "Dynamax": plain(dynamax=True),
    "Tandemaus": plain(sids=["tandemaus"]),
    "far": plain(far=True),
    # HashTagAJay's pile (to CyrillJan)
    "H plain": plain(account=TAKER),
    "H Luckydex is CyrillJan's: none": plain(account=TAKER, sids=["machop"]),
    "H Old": plain(account=TAKER, caught=OLD),
    "H medal Rattata": plain(account=TAKER, sids=["rattata"], size="xs", kg=2.1),
    "H Rattata too heavy": plain(account=TAKER, sids=["rattata"], size="xs", kg=3.0),
    "H Rattata not small": plain(account=TAKER, sids=["rattata"], size="", kg=2.1),
    "H Rattata size not read": plain(account=TAKER, sids=["rattata"], size=None, kg=2.1),
    "H Rattata weight misread": plain(account=TAKER, sids=["rattata"], size="xxs", kg=21.0),
    "H medal Magikarp": plain(account=TAKER, sids=["magikarp"], kg=14.0),
    "H 2XL": plain(account=TAKER, candy_xl=120),
    "H 2XL beats GIV": plain(account=TAKER, sids=["rhyhorn"], candy_xl=120),
    "H Candy XL not read": plain(account=TAKER, candy_xl=None),
    "H XXL skips 2XL": plain(account=TAKER, size="xxl", candy_xl=120),
    "H GIV": plain(account=TAKER, sids=["rhyhorn"]),
    "H XLX at 29": plain(account=TAKER, levels=[29]),
    "H not XLX at 27": plain(account=TAKER, levels=[27]),
    "H Dynamax, has one": plain(account=TAKER, dynamax=True),
    "H Dynamax, has none": plain(account=TAKER, sids=["wooloo"], dynamax=True),
    "H Tandemaus": plain(account=TAKER, sids=["tandemaus"]),
    "H far": plain(account=TAKER, far=True),
}


def answer(f):
    f, t = f if isinstance(f, tuple) else (f, TABLES[v.TO.get(f.account, TAKER)])
    r = v.final_tag(f, t, TODAY)
    return [r.kind, list(r.tags), r.name, r.why]


def main():
    got = {k: answer(f) for k, f in CASES.items()}
    if "--record" in sys.argv:
        json.dump(got, open(GOLD, "w"), indent=1, ensure_ascii=False)
        print(f"recorded {len(got)} verdicts -> {GOLD}")
        return 0
    gold = json.load(open(GOLD))
    bad = [k for k in sorted(set(got) | set(gold)) if got.get(k) != gold.get(k)]
    for k in bad:
        print(f"{k}:\n  was {gold.get(k)}\n  now {got.get(k)}")
    if bad:
        print(f"{len(bad)} of {len(got)} verdicts changed")
        return 1
    print(f"all {len(got)} verdicts the same")
    return 0


if __name__ == "__main__":
    sys.exit(main())
