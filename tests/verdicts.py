#!/usr/bin/env python3
"""Pins the final tag skills/shared/verdict.py gives each made-up Pokémon. No phone, no data files: the species lists
here are made up too, so only the rules and their order are tested.

  python3 tests/verdicts.py            check every case against tests/verdicts.json
  python3 tests/verdicts.py --record   write verdicts.json from today's code (after a change you meant)
"""
import datetime, json, os, sys
from dataclasses import replace

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
    TAKER: {"to": TAKER, "why": {"MACHOP_NORMAL": ("Luckydex", "lucky dex hole"), "NIDORAN_FEMALE_NORMAL": ("Luckydex", "lucky dex hole"),
                                 "RHYHORN_NORMAL": ("Reroll", "#1 raid attacker"), "GEODUDE_NORMAL": ("Reroll", "PvP"),
                                 "MAGIKARP_NORMAL": ("Reroll", "★100% hole"), "TANDEMAUS_NORMAL": ("Reroll", "family of 3")},
            "lucky": {"NIDORAN_FEMALE_NORMAL": "female"}, "evolved": {"GOLEM_NORMAL": "stage 2"}, "no_dmax": set(),
            "xl_full": set(), "raid": {"RHYHORN_NORMAL", "RHYDON_NORMAL"}, "raid_self": {"RHYDON_NORMAL"}, "strong": {"DRILBUR_NORMAL"},
            "hard": {}, "by_hand": set(), "dmax": {"WOOLOO_NORMAL": 480, "DUBWOOL_NORMAL": 480},
            "team_xl": {"BAGON_NORMAL": [1440, "SALAMENCE_NORMAL", 4], "TRAPINCH_NORMAL": None},
            "team_line": {"BAGON_NORMAL", "SHELGON_NORMAL", "SALAMENCE_NORMAL", "TRAPINCH_NORMAL", "VIBRAVA_NORMAL", "FLYGON_NORMAL"}},
    GIVER: {"to": GIVER, "why": {"RHYHORN_NORMAL": ("GIV", "PvP"),
                                 "BULBASAUR_NORMAL": ("Reroll", "Venusaur can mega")}, "lucky": {}, "evolved": {"GOLEM_NORMAL": "stage 2"},
            "no_dmax": set(), "xl_full": set(), "raid": {"RHYHORN_NORMAL", "RHYDON_NORMAL"}, "raid_self": {"RHYDON_NORMAL"}, "strong": {"DRILBUR_NORMAL"},
            "hard": {"GIBLE_NORMAL": "10 km egg (Gible)", "SMEARGLE_NORMAL": "hard to farm"}, "by_hand": {"SPINDA_00", "TAUROS_NORMAL"},
            "dmax": {"WOOLOO_NORMAL": 480, "DUBWOOL_NORMAL": 480}, "team_xl": {"BAGON_NORMAL": [1800, "SALAMENCE_NORMAL", 5], "TRAPINCH_NORMAL": None}},
}


def cyrill(team=None, **xl):
    """HashTagAJay's tables with CyrillJan's Candy XL {sid: n} and Team Future/Ideal bars (team_xl_need's shape)"""
    return {**TABLES[GIVER], "cyrill_xl": {s: (n, "2026-11-25 12:00:00") for s, n in xl.items()},
            "cyrill_team_xl": team or {}}


def plain(**kw):
    """an untraded, new, ordinary, under-26 Pokémon that fits no rule, with every fact read"""
    d = dict(account=GIVER, sids=["PIDGEY_NORMAL"], iv_sum=30, traded=False, caught=NEW, gender="male", size="",
             kg=1.0, candy_xl=400, candy=2000, levels=[20], far=False, gym_top20=None)
    d.update(kw)
    return Facts(**d)


CASES = {
    # never Transfer by default: a fact not read -> unsure
    "plain": plain(),
    "no account": plain(account=None),
    "no appraisal": plain(iv_sum=None),
    "98%": plain(iv_sum=44),
    "species not read": plain(sids=None),
    "two species": plain(sids=["PIDGEY_NORMAL", "RATTATA_NORMAL"]),
    "two forms": plain(sids=["RATTATA_NORMAL", "RATTATA_ALOLA"]),
    "traded not read": plain(traded=None),
    "catch date not read": plain(caught=None),
    "size not read": plain(size=None),
    "level not read": plain(levels=None),
    "level 25 or 26": plain(levels=[25.5, 26]),
    "distance not checked": plain(far=None),
    "no species lists": (plain(sids=["MACHOP_NORMAL"]), {"to": TAKER, "missing": "no a lucky /dex run for HashTagAJay yet"}),
    # by hand, for now
    "your tag": plain(other_tags=["Evo"]),
    "the TODO tag (/mega)": plain(other_tags=["TODO"]),
    "your tags, as read": plain(other_tags=["OLD", "GUARANTEEDLUCKY"]),
    "the CPD tag, ignored": plain(other_tags=["CPD"]),
    "the CPD tag, traded": plain(traded=True, other_tags=["CPD"]),
    "CPD and Evo, Evo counts": plain(other_tags=["CPD", "Evo"]),
    "your tag GIV, untraded": plain(other_tags=["GIV"]),
    "your tag, traded or not not read": plain(other_tags=["Old"], traded=None),
    "traded, trade tags come off": plain(traded=True, other_tags=["GIV", "XLX"]),
    "traded Machoke, Old comes off": plain(sids=["MACHOKE_NORMAL"], traded=True, other_tags=["Old"]),
    "traded, your tag Evo": plain(traded=True, other_tags=["Evo"]),
    "traded, a tag no rule knows": plain(traded=True, other_tags=["Mine"]),
    "untraded, Remote Trade and RT": plain(other_tags=["REMOTE TRADE", "RT"]),
    "untraded, RT only (hidden from a partner)": plain(other_tags=["RT"]),
    "traded, Remote Trade and RT come off": plain(traded=True, other_tags=["REMOTE TRADE", "RT"]),
    "shadow": plain(shadow=True),
    "lucky": plain(lucky=True),
    "costume": plain(costume=True),
    "background": plain(background=True),
    "shiny, untraded, doesn't qualify": plain(shiny=True),
    "shiny, untraded, already has Remote Trade and RT": plain(shiny=True, other_tags=["REMOTE TRADE", "RT"]),
    "shiny, 98%, already has Remote Trade and RT": plain(shiny=True, iv_sum=45, other_tags=["REMOTE TRADE", "RT"]),
    "shiny, untraded, Remote Trade and a tag no rule knows": plain(shiny=True, other_tags=["REMOTE TRADE", "Mine"]),
    "shiny, traded, doesn't qualify, tags come off": plain(shiny=True, traded=True, other_tags=["GIV", "SOMETHING"]),
    "shiny, 98%": plain(shiny=True, iv_sum=45),
    "Minior, shiny not read: none is shiny": plain(sids=["MINIOR_BLUE"], shiny=None),
    "Minior read as shiny: none is shiny": plain(sids=["MINIOR_BLUE", "minior_meteor"], shiny=True),
    "shiny lucky, traded, a top IV": plain(shiny=True, lucky=True, traded=True, iv_top=True),
    "shiny lucky, traded, out, judged by /ivc": plain(shiny=True, lucky=True, traded=True, iv_top=False, pvp_judged=True, ivc_judged=True),
    "shiny lucky, not ranked yet: to /ivc first": plain(shiny=True, lucky=True, traded=True),
    "shiny and Gigantamax": plain(shiny=True, gigantamax=True),
    "costume favorite": plain(costume=True, favorite=True),
    "costume favorite, star not read": plain(costume=True, favorite=None),
    "costume favorite, 93%: its IV name": plain(costume=True, favorite=True, iv_sum=42, ivs=(14, 14, 14)),
    "costume favorite traded, trade tags come off": plain(costume=True, favorite=True, traded=True, other_tags=["GIV", "Reroll"]),
    "costume favorite, caught 2017: no GuaranteedLucky": plain(costume=True, favorite=True, caught=datetime.date(2017, 7, 1)),
    "costume favorite shiny, untraded: no Remote Trade": plain(shiny=True, costume=True, favorite=True),
    "costume favorite shadow": plain(shadow=True, costume=True, favorite=True, ivs=(10, 10, 10)),
    "costume favorite lucky, out of the top IV": plain(lucky=True, costume=True, favorite=True, iv_top=False, pvp_judged=True, ivs=(10, 10, 10)),
    "costume favorite on a raid team": plain(costume=True, favorite=True, raid_team=["Boss A (party 1)"]),
    "costume not a favorite, traded: Transfer": plain(costume=True, favorite=False, traded=True),
    "shiny shadow, no purify": plain(shiny=True, shadow=True, sids=["RHYHORN_NORMAL"], ivs=(10, 10, 10), pure_top=False),
    # the user's rules for an untraded shadow, costume or background one; a traded one is judged like any traded one
    "shiny search failed": plain(shiny=None),
    "costume search failed": plain(costume=None),
    "background search failed": plain(background=None),
    "shadow, IVs not read": plain(shadow=True, ivs=None),
    "shadow, purified 100%": plain(shadow=True, iv_sum=39, ivs=(13, 13, 13)),
    "shadow, purified 98%": plain(shadow=True, iv_sum=38, ivs=(13, 13, 12)),
    "shadow, purified 93%": plain(shadow=True, iv_sum=36, ivs=(12, 12, 12)),
    "shadow raid attacker": plain(shadow=True, sids=["RHYHORN_NORMAL"], ivs=(10, 10, 10)),
    "shadow raid attacker, ranked out once purified": plain(shadow=True, sids=["RHYHORN_NORMAL"], ivs=(10, 10, 10), pure_top=False),
    "shadow raid attacker, ranked out, under 360 XL": plain(shadow=True, sids=["RHYHORN_NORMAL"], ivs=(10, 10, 10), pure_top=False, candy_xl=0),
    "shadow raid attacker, top once purified": plain(shadow=True, sids=["RHYHORN_NORMAL"], ivs=(10, 10, 10), pure_top=True),
    "shadow, under 360 XL": plain(shadow=True, ivs=(10, 10, 10), candy_xl=0),
    "strong-line shadow": plain(shadow=True, sids=["DRILBUR_NORMAL"], ivs=(10, 10, 10)),
    "strong-line shadow, old": plain(shadow=True, sids=["DRILBUR_NORMAL"], ivs=(10, 10, 10), pure_top=False, caught=OLD),
    "strong-line shadow, 2019 catch": plain(shadow=True, sids=["DRILBUR_NORMAL"], ivs=(10, 10, 10), pure_top=False, caught=LUCKY),
    "shadow, 360+ XL": plain(shadow=True, ivs=(10, 10, 10)),
    "shadow, XL not read": plain(shadow=True, ivs=(10, 10, 10), candy_xl=None),
    "shadow, under 360 XL, 2019 catch": plain(shadow=True, ivs=(10, 10, 10), candy_xl=0, caught=LUCKY),
    "shadow, 360+ XL, 2019 catch": plain(shadow=True, ivs=(10, 10, 10), caught=LUCKY),
    "shadow, under 360 XL, old": plain(shadow=True, ivs=(10, 10, 10), candy_xl=0, caught=OLD),
    "shadow, 360+ XL, old": plain(shadow=True, ivs=(10, 10, 10), caught=OLD),
    "shadow xxs, old still IVC": plain(shadow=True, ivs=(10, 10, 10), size="xxs", caught=OLD),
    "H shadow, old": plain(account=TAKER, shadow=True, ivs=(10, 10, 10), caught=OLD),
    "shiny shadow, 2019 catch": plain(shiny=True, shadow=True, sids=["RHYHORN_NORMAL"], ivs=(10, 10, 10), pure_top=False, caught=LUCKY),
    "shadow, no species lists": (plain(shadow=True, ivs=(10, 10, 10)), {"to": TAKER, "missing": "no roster"}),
    "shadow legendary": plain(shadow=True, sids=["ENTEI_NORMAL"], ivs=(10, 10, 10)),
    "shadow costume": plain(shadow=True, costume=True, ivs=(10, 10, 10)),
    "shadow background": plain(shadow=True, background=True, ivs=(10, 10, 10)),
    "costume 93%": plain(costume=True, iv_sum=42),
    "costume 96%": plain(costume=True, iv_sum=43),
    "costume raid attacker line": plain(costume=True, sids=["RHYHORN_NORMAL"]),
    "costume raid attacker line, can't evolve": plain(costume=True, sids=["RHYHORN_NORMAL"], evolves=False),
    "costume raid attacker line, can't evolve, under 360 XL": plain(costume=True, sids=["RHYHORN_NORMAL"], evolves=False,
                                                                    candy_xl=0),
    "costume raid attacker line, can evolve": plain(costume=True, sids=["RHYHORN_NORMAL"], evolves=True),
    "costume, under 360 XL": plain(costume=True, candy_xl=0),
    "costume, XL not read": plain(costume=True, candy_xl=None),
    "costume traded": plain(costume=True, traded=True),
    "background traded": plain(background=True, traded=True),
    "lucky traded": plain(lucky=True, traded=True),
    "lucky traded 93%": plain(lucky=True, traded=True, iv_sum=42),
    # the lucky rule: only /ivc ranks it
    "lucky, /ivc couldn't rank it": plain(lucky=True, ivc_judged=True),
    "lucky, /pvpc can't rank it": plain(lucky=True, pvp_judged=True),
    "lucky top IV": plain(lucky=True, iv_top=True, ivc_judged=True),
    "lucky out, no PvP": plain(lucky=True, iv_top=False, ivc_judged=True, ivs=(10, 10, 10)),
    "lucky out, /pvpc said no": plain(lucky=True, iv_top=False, pvp_judged=True, ivs=(10, 10, 10)),
    "lucky costume out, /pvpc said no": plain(lucky=True, costume=True, iv_top=False, pvp_judged=True, ivs=(10, 10, 10)),
    "lucky background out, /pvpc said no": plain(lucky=True, background=True, iv_top=False, pvp_judged=True,
                                                 ivs=(10, 10, 10)),
    "lucky costume traded out, /pvpc said no": plain(lucky=True, costume=True, traded=True, iv_top=False,
                                                     pvp_judged=True, ivs=(10, 10, 10)),
    "H shadow, under 360 XL": plain(account=TAKER, shadow=True, ivs=(10, 10, 10), candy_xl=0),
    "gigantamax": plain(gigantamax=True),
    "mythical": plain(sids=["MEW_NORMAL"]),
    "mythical from a raid": plain(sids=["MEW_NORMAL"], raid=True),
    "mythical not from a raid": plain(sids=["MEW_NORMAL"], raid=False),
    # trades.py's legendary rules
    "legendary untraded": plain(sids=["ENTEI_NORMAL"]),
    "legendary untraded old": plain(sids=["ENTEI_NORMAL"], caught=OLD),
    "legendary traded": plain(sids=["ENTEI_NORMAL"], traded=True),
    "legendary fused": plain(sids=["KYUREM_BLACK"]),
    "meltan": plain(sids=["MELTAN_NORMAL"]),
    "meltan traded": plain(sids=["MELTAN_NORMAL"], traded=True),
    "melmetal traded": plain(sids=["MELMETAL_NORMAL"], traded=True),
    "ultra beast": plain(sids=["NIHILEGO_NORMAL"]),
    # gym defenders
    "gym not checked": plain(sids=["SNORLAX_NORMAL"]),
    "gym top 20": plain(sids=["SNORLAX_NORMAL"], gym_top20=True),
    "gym not top 20": plain(sids=["SNORLAX_NORMAL"], gym_top20=False),
    "gym top 20 traded": plain(sids=["SNORLAX_NORMAL"], gym_top20=True, traded=True),
    # raid teams (raidteams.on_team's answer): the holder's own team keeps, before every Transfer and GIV
    "raid team": plain(sids=["RHYHORN_NORMAL"], raid_team=["Mega Venusaur (party 1)"]),
    "raid team, many bosses": plain(sids=["RHYHORN_NORMAL"], raid_team=[f"Boss {i} (party 1)" for i in range(5)]),
    "raid team traded": plain(sids=["RHYHORN_NORMAL"], raid_team=["Mega Venusaur (party 1)"], traded=True),
    "raid team traded, GIV comes off": plain(sids=["RHYHORN_NORMAL"], raid_team=["Mega Venusaur (party 1)"], traded=True,
                                             other_tags=["GIV"]),
    "raid team shadow": plain(sids=["RHYHORN_NORMAL"], raid_team=["Mega Venusaur (party 1)"], shadow=True, ivs=(10, 10, 10)),
    "raid team, your tag stays": plain(sids=["RHYHORN_NORMAL"], raid_team=["Mega Venusaur (party 1)"], other_tags=["Old"]),
    "raid team: on none": plain(sids=["RHYHORN_NORMAL"], raid_team=[]),
    "raid team: on none, Transfer": plain(raid_team=[]),
    "raid team: not sure": plain(raid_team=None),
    "raid team: no count": plain(raid_team=()),
    # the order, CyrillJan's pile (to HashTagAJay)
    "traded": plain(traded=True),
    "traded Machoke: Evo": plain(sids=["MACHOKE_NORMAL"], traded=True),
    "H traded Machoke: Transfer": plain(account=TAKER, sids=["MACHOKE_NORMAL"], traded=True),
    "legendary XXL": plain(sids=["ENTEI_NORMAL"], size="xxl"),
    "legendary size not read": plain(sids=["ENTEI_NORMAL"], size=None),
    "H size not read, under 360 XL": plain(account=TAKER, size=None, candy_xl=120),
    "2019 catch": plain(caught=LUCKY),
    "2019 catch, Luckydex": plain(sids=["MACHOP_NORMAL"], caught=LUCKY),
    "Luckydex": plain(sids=["MACHOP_NORMAL"], caught=OLD),
    "Luckydex wrong gender": plain(sids=["NIDORAN_FEMALE_NORMAL"], gender="male"),
    "Luckydex right gender": plain(sids=["NIDORAN_FEMALE_NORMAL"], gender="female"),
    "Luckydex gender not read": plain(sids=["NIDORAN_FEMALE_NORMAL"], gender=None),
    "Old": plain(caught=OLD),
    "Old beats Reroll": plain(sids=["RHYHORN_NORMAL"], caught=OLD),
    "Reroll": plain(sids=["RHYHORN_NORMAL"]),
    "GIV": plain(sids=["GEODUDE_NORMAL"], levels=[30]),
    "XXL": plain(size="xxl", levels=[30]),
    "xxs": plain(size="xxs"),
    "XLX": plain(levels=[26, 26.5]),
    "XLX beats evolved": plain(sids=["GOLEM_NORMAL"], levels=[27]),
    "evolved": plain(sids=["GOLEM_NORMAL"]),
    "Dynamax": plain(dynamax=True),
    "Tandemaus": plain(sids=["TANDEMAUS_NORMAL"]),
    "far": plain(far=True),
    # CyrillJan short of the family's candy: GIV, the trade's candy (the user, 2026-11-23)
    "C no team line, under 360 XL, Candy not read: unsure": plain(candy_xl=0, candy=None),
    "C no team line, under 360 XL, 400 Candy: Transfer": plain(candy_xl=0, candy=400),
    "C no team line, under 360 XL, XL not read, 400 Candy: Transfer": plain(candy_xl=None, candy=400),
    "C no team line, under 360 XL, under 348 Candy: GIV": plain(candy_xl=0, candy=100),
    "C team line, 4 100s, 1000 XL: GIV": plain(sids=["BAGON_NORMAL"], candy_xl=1000, xl=1000),
    "C team line, 4 100s, 1500 XL: Transfer": plain(sids=["BAGON_NORMAL"], candy_xl=1500, xl=1500),
    "C team line, under 360 XL: GIV": plain(sids=["BAGON_NORMAL"], candy_xl=100, xl=100, candy=None),
    "C team line, XL count not read: unsure": plain(sids=["BAGON_NORMAL"], candy_xl=360, xl=None),
    "C team line, 100s not counted: unsure": plain(sids=["TRAPINCH_NORMAL"], candy_xl=1000, xl=1000),
    "H team line, 5 100s, 1000 XL: GIV": plain(account=TAKER, sids=["BAGON_NORMAL"], candy_xl=1000, xl=1000),
    "H team line, 5 100s, 1900 XL: Transfer": plain(account=TAKER, sids=["BAGON_NORMAL"], candy_xl=1900, xl=1900),
    "H team line, 100s not counted: unsure": plain(account=TAKER, sids=["TRAPINCH_NORMAL"], candy_xl=1000, xl=1000),
    "C under 348 Candy: GIV": plain(candy=347),
    "C 348 Candy, 360+ XL: Transfer": plain(candy=348),
    "C Candy not read: unsure": plain(candy=None),
    "C Candy XL not read: unsure": plain(candy_xl=None),
    "C short, traded: Transfer": plain(candy=10, candy_xl=0, traded=True),
    "C short, xxs: IVC": plain(candy=10, size="xxs"),
    "C short, Reroll first": plain(sids=["GEODUDE_NORMAL"], candy=10),
    "H short of candy: Transfer": plain(account=TAKER, candy=10),
    # HashTagAJay's pile (to CyrillJan)
    "H plain": plain(account=TAKER),
    "H Luckydex is CyrillJan's: none": plain(account=TAKER, sids=["MACHOP_NORMAL"]),
    "H Old": plain(account=TAKER, caught=OLD),
    "H medal Rattata": plain(account=TAKER, sids=["RATTATA_NORMAL"], size="xs", kg=2.1),
    "H Rattata too heavy": plain(account=TAKER, sids=["RATTATA_NORMAL"], size="xs", kg=3.0),
    "H Rattata not small": plain(account=TAKER, sids=["RATTATA_NORMAL"], size="", kg=2.1),
    "H Rattata size not read": plain(account=TAKER, sids=["RATTATA_NORMAL"], size=None, kg=2.1),
    "H Rattata weight misread": plain(account=TAKER, sids=["RATTATA_NORMAL"], size="xxs", kg=21.0),
    "H medal Magikarp": plain(account=TAKER, sids=["MAGIKARP_NORMAL"], kg=14.0),
    "H 2XL": plain(account=TAKER, candy_xl=120),
    "H 2XL beats GIV": plain(account=TAKER, sids=["RHYHORN_NORMAL"], candy_xl=120),
    "H Candy XL not read": plain(account=TAKER, candy_xl=None),
    "H XXL skips 2XL": plain(account=TAKER, size="xxl", candy_xl=120),
    "H xxs skips 2XL": plain(account=TAKER, size="xxs", candy_xl=120),
    "XXL traded": plain(size="xxl", traded=True),
    "XXL traded, trade tags come off": plain(size="xxl", traded=True, other_tags=["GIV", "XLX"]),
    "XXL old, Old comes off": plain(size="xxl", caught=OLD, other_tags=["OLD", "EVO"]),
    "XXL 2016, no GuaranteedLucky": plain(size="xxl", caught=LUCKY),
    "XXL lucky": plain(size="xxl", traded=True, lucky=True),
    "XXL shadow": plain(size="xxl", shadow=True),
    "XXL shiny traded, Transfer comes off": plain(size="xxl", traded=True, shiny=True, other_tags=["TRANSFER"]),
    "XXL, IVC comes off": plain(size="xxl", other_tags=["IVC"]),
    "XXL, 2XL reads as XL": plain(size="xxl", other_tags=["XL"]),
    "xxs traded still Transfer": plain(size="xxs", traded=True),
    "xxs untraded still IVC": plain(size="xxs", levels=[30]),
    "H GIV": plain(account=TAKER, sids=["RHYHORN_NORMAL"]),
    "H XLX at 29": plain(account=TAKER, levels=[29]),
    "H not XLX at 27": plain(account=TAKER, levels=[27]),
    # the level 26+ GIV only while CyrillJan is short of Candy XL of the line (the user, 2026-11-25)
    "H 26+, CyrillJan 359 XL: GIV": (plain(account=TAKER, levels=[29]), cyrill(PIDGEY_NORMAL=359)),
    "H 26+, CyrillJan 360 XL: Transfer": (plain(account=TAKER, levels=[29]), cyrill(PIDGEY_NORMAL=360)),
    "H 26+, CyrillJan 360 XL, far: GIV far": (plain(account=TAKER, levels=[29], far=True), cyrill(PIDGEY_NORMAL=360)),
    "H level 25 or 26, CyrillJan full: Transfer": (plain(account=TAKER, levels=[25.5, 26]), cyrill(PIDGEY_NORMAL=400)),
    "H 26+, team line, 2 100s, 700 XL: GIV": (plain(account=TAKER, sids=["GIBLE_NORMAL"], levels=[29]),
                                               cyrill(team={"GIBLE_NORMAL": [720, "GARCHOMP_NORMAL", 2]}, GIBLE_NORMAL=700)),
    "H 26+, team line, 2 100s, 720 XL: no level GIV": (plain(account=TAKER, sids=["GIBLE_NORMAL"], levels=[29]),
                                                         cyrill(team={"GIBLE_NORMAL": [720, "GARCHOMP_NORMAL", 2]}, GIBLE_NORMAL=720)),
    "H 26+, team line, CyrillJan's 100s not counted: GIV": (plain(account=TAKER, levels=[29]),
                                                             cyrill(team={"PIDGEY_NORMAL": None}, PIDGEY_NORMAL=5000)),
    "XLX, CyrillJan's own: no XL check": (plain(levels=[29]), {**TABLES[TAKER], "cyrill_xl": {"PIDGEY_NORMAL": (5000, "")}}),
    "H Dynamax, has one": plain(account=TAKER, dynamax=True),
    "H Dynamax, has none": plain(account=TAKER, sids=["WOOLOO_NORMAL"], dynamax=True),
    "H Tandemaus": plain(account=TAKER, sids=["TANDEMAUS_NORMAL"]),
    "H far": plain(account=TAKER, far=True),
    # a family with an evolution over 100 candy: GIV where it would get Transfer, untraded (the user, 2026-11-12)
    "Snom: GIV": plain(sids=["SNOM_NORMAL"]),
    "H Snom: GIV": plain(account=TAKER, sids=["SNOM_NORMAL"]),
    "Noivern: GIV": plain(sids=["NOIVERN_NORMAL"]),
    "H Magikarp, no medal: GIV": plain(account=TAKER, sids=["MAGIKARP_NORMAL"], kg=5.0),
    # its holder has 5000+ Candy of it: the trade's candy isn't needed (the user, 2026-11-25)
    "H Magikarp, 5000 Candy: Transfer": plain(account=TAKER, sids=["MAGIKARP_NORMAL"], kg=5.0, candy=5000),
    "H Magikarp, 4999 Candy: GIV": plain(account=TAKER, sids=["MAGIKARP_NORMAL"], kg=5.0, candy=4999),
    "H Magikarp, Candy not read: unsure": plain(account=TAKER, sids=["MAGIKARP_NORMAL"], kg=5.0, candy=None),
    "Snom, 6000 Candy: Transfer": plain(sids=["SNOM_NORMAL"], candy=6000),
    "Snom xxs: IVC": plain(sids=["SNOM_NORMAL"], size="xxs"),
    "Snom at 30: XLX first": plain(sids=["SNOM_NORMAL"], levels=[30]),
    "H Snom at 29: XLX first": plain(account=TAKER, sids=["SNOM_NORMAL"], levels=[29]),
    "traded Snom: Transfer": plain(sids=["SNOM_NORMAL"], traded=True),
    "shadow Snom: Transfer": plain(sids=["SNOM_NORMAL"], shadow=True, ivs=(10, 10, 10)),
    "Charmander, 100 candy: Transfer": plain(sids=["CHARMANDER_NORMAL"]),
    "Karrablast, trade evolution: Transfer": plain(sids=["KARRABLAST_NORMAL"]),
    "H Karrablast, trade evolution: GIV": plain(account=TAKER, sids=["KARRABLAST_NORMAL"]),
    "Roggenrola: GIV": plain(sids=["ROGGENROLA_NORMAL"]),
    "Boldore, trade evolution: Transfer": plain(sids=["BOLDORE_NORMAL"]),
    # HashTagAJay's Leftovers, judged for any account (the user, 2026-11-16)
    "H XLX at 26": plain(account=TAKER, levels=[26]),
    "H level 25 or 26": plain(account=TAKER, levels=[25.5, 26]),
    "H Reroll, a mega line": plain(account=TAKER, sids=["BULBASAUR_NORMAL"]),
    "H 2XL beats Reroll": plain(account=TAKER, sids=["BULBASAUR_NORMAL"], candy_xl=120),
    "H Old beats Reroll": plain(account=TAKER, sids=["BULBASAUR_NORMAL"], caught=OLD),
    "H Reroll beats XLX": plain(account=TAKER, sids=["BULBASAUR_NORMAL"], levels=[30]),
    "H can Dynamax, counts not read": plain(account=TAKER, sids=["WOOLOO_NORMAL"]),
    # one that can Dynamax but isn't one: GIV while the account is short of Candy or Candy XL (the user, 2026-11-16)
    "H can Dynamax, few candy: GIV": plain(account=TAKER, sids=["WOOLOO_NORMAL"], candy=1000, xl=900),
    "H can Dynamax, few XL: GIV": plain(account=TAKER, sids=["WOOLOO_NORMAL"], candy=3000, xl=480),
    "H can Dynamax, enough: Transfer": plain(account=TAKER, sids=["WOOLOO_NORMAL"], candy=1001, xl=481),
    "H can Dynamax, enough but far: GIV": plain(account=TAKER, sids=["WOOLOO_NORMAL"], candy=3000, xl=900, far=True),
    "H can Dynamax, enough but 26: XLX": plain(account=TAKER, sids=["WOOLOO_NORMAL"], candy=3000, xl=900, levels=[26]),
    "H can Dynamax, short but 2XL first": plain(account=TAKER, sids=["WOOLOO_NORMAL"], candy=100, xl=100, candy_xl=0),
    "H Dynamax, enough candy: GIV": plain(account=TAKER, sids=["WOOLOO_NORMAL"], dynamax=True, candy=3000, xl=900),
    "C can Dynamax, few candy: GIV": plain(sids=["DUBWOOL_NORMAL"], candy=40, xl=0),
    "C can Dynamax, enough: Transfer": plain(sids=["DUBWOOL_NORMAL"], candy=3000, xl=900),
    "C can Dynamax, counts not read": plain(sids=["DUBWOOL_NORMAL"]),
    "C Dynamax, enough candy: GIV": plain(sids=["DUBWOOL_NORMAL"], dynamax=True, candy=3000, xl=900),
    "H 10 km egg family: GIV": plain(account=TAKER, sids=["GIBLE_NORMAL"]),
    "H XLX beats the egg GIV": plain(account=TAKER, sids=["GIBLE_NORMAL"], levels=[26]),
    "H Smeargle: GIV": plain(account=TAKER, sids=["SMEARGLE_NORMAL"]),
    "H Spinda: by hand": plain(account=TAKER, sids=["SPINDA_00"]),
    "H old regional: by hand": plain(account=TAKER, sids=["TAUROS_NORMAL"], caught=OLD),
    "H 2016 regional: by hand": plain(account=TAKER, sids=["TAUROS_NORMAL"], caught=LUCKY),
    "H traded regional: Transfer": plain(account=TAKER, sids=["TAUROS_NORMAL"], traded=True),
    "regional to HashTagAJay: as before": plain(sids=["TAUROS_NORMAL"]),
}


def answer(f):
    f, t = f if isinstance(f, tuple) else (f, TABLES[v.TO.get(f.account, TAKER)])
    r = v.final_tag(f, t, TODAY)
    return [r.kind, list(r.tags), r.name, r.why] + ([{"off": list(r.off)}] if r.off else []) \
        + (["purify"] if r.purify else []) + (["star"] if r.star else []) \
        + (["clear"] if r.clear else []) + (["unstar"] if r.unstar else [])


import raidteams  # noqa: E402
import door  # noqa: E402

TEAMS = {"bars": {"RHYHORN_NORMAL": 1500, "RHYHORN_NORMAL|shadow": 1400, "PIDGEY_NORMAL": None},  # made up: a count's teams.json
         "copies": [{"species": ["RHYHORN_NORMAL"], "shadow": False, "cp": 2000, "hp": 150, "kg": 110.5, "m": 1.02,
                     "on": ["Boss A (party 1)"]},
                    {"species": ["RHYHORN_NORMAL"], "shadow": False, "cp": 1800, "hp": 140, "kg": 99.1, "m": 0.95, "on": []},
                    {"species": ["RHYHORN_NORMAL"], "shadow": True, "cp": 1900, "hp": 145, "kg": 120.0, "m": 1.1,
                     "on": ["Boss B (party 2)"]},
                    {"species": ["RHYHORN_NORMAL"], "shadow": False, "cp": 1600, "hp": 120, "kg": None, "m": None,
                     "on": ["Boss A (party 1)"]},
                    {"species": ["RHYHORN_NORMAL"], "shadow": False, "cp": 1600, "hp": 120, "kg": None, "m": None, "on": []}],
         "stars": {"RHYHORN_NORMAL": [[36, 2050]]}}  # walked with 3*,4* from CP2050 down
TEAM_CASES = {  # (sids, shadow, cp, hp, kg, m[, iv_sum]) -> raidteams.on_team
    "on, by kg and m": (["RHYHORN_NORMAL"], False, 2000, 150, 110.5, 1.02),
    "on, powered up since (kg and m)": (["RHYHORN_NORMAL"], False, 2300, 165, 110.51, 1.02),
    "off, by kg and m": (["RHYHORN_NORMAL"], False, 1800, 140, 99.1, 0.95),
    "shadow, on": (["RHYHORN_NORMAL"], True, 1900, 145, 120.0, 1.1),
    "no kg: by CP and HP": (["RHYHORN_NORMAL"], False, 2000, 150, None, None),
    "a list read: CP only": (["RHYHORN_NORMAL"], False, 1800, None, None, None),
    "twins, one on, one off": (["RHYHORN_NORMAL"], False, 1600, 120, None, None),
    "not in the count, over the bar": (["RHYHORN_NORMAL"], False, 2100, 151, 105.0, 1.0),
    "not in the count, under the bar": (["RHYHORN_NORMAL"], False, 1400, 110, 105.0, 1.0),
    "shadow under its bar": (["RHYHORN_NORMAL"], True, 1300, 110, 105.0, 1.0),
    "no copy can make a team": (["PIDGEY_NORMAL"], False, 300, 50, 1.0, 0.3),
    "on no boss list": (["MAGIKARP_NORMAL"], False, 100, 20, 10.0, 0.9),
    "species not sure, one on a list": (["RHYHORN_NORMAL", "PIDGEY_NORMAL"], False, 1000, 100, None, None),
    "species not sure, none on a list": (["PIDGEY_NORMAL", "MAGIKARP_NORMAL"], False, 300, 50, None, None),
    "CP not read, not in the count": (["RHYHORN_NORMAL"], False, None, 150, 105.0, 1.0),
    "over the bar, 2* under the star search": (["RHYHORN_NORMAL"], False, 2000, 149, 105.0, 1.0, 36),
    "over the bar, 3*: the star search had it": (["RHYHORN_NORMAL"], False, 2000, 149, 105.0, 1.0, 37),
    "2*, over the star search's start": (["RHYHORN_NORMAL"], False, 2100, 151, 105.0, 1.0, 30),
    "2*, a shadow: its pile had no star search": (["RHYHORN_NORMAL"], True, 2000, 149, 105.0, 1.0, 30),
}


BOTTOM = ("traded", "caught", "far")  # the facts off the page's bottom (door.page_facts)
COUNTS = ("candy", "xl", "candy_xl")  # the counts: on the top screen, or (a Dynamax page) a drag down


def part_said(f):
    """what the door walk's part (door.Door.splits, on a pile whose search says nothing of trades or ages) that f is in
    tells the door instead of the page's bottom. f's traded or catch date not known: nothing"""
    class Pile:
        terms, said = {"#giv"}, {}
        narrow = lambda self, known: known
    age = f.caught and v.age_of(f.caught, TODAY)
    for terms, known in door.Door.splits(Pile()):
        if f.traded is not None and ("traded" in terms.split("&")) == f.traded and known.get("age", age) == age:
            break
    else:
        known = {}
    return {"traded": known.get("traded"), "age": known.get("age"), "caught": None, "far": None}


def top_only():
    """the door asks the rules first with the page's bottom not read (and the counts too, for a Dynamax page), and
    drags down only when that answer is unsure: so each answer without them must be unsure or the one with them"""
    bad = []
    for k, c in CASES.items():
        f, t = c if isinstance(c, tuple) else (c, None)
        full = answer(c)
        split = part_said(f)
        for gone in (BOTTOM, COUNTS, BOTTOM + COUNTS, split, {**split, **dict.fromkeys(COUNTS)}):
            g = replace(f, **(gone if isinstance(gone, dict) else dict.fromkeys(gone)))
            if f.lucky:
                g = replace(g, traded=True)  # (the door knows a lucky one is traded without the bottom)
            got = answer((g, t) if t else g)
            same = (lambda r: r[:3] + r[4:]) if isinstance(gone, dict) else (lambda r: r)  # (a bucket's why says less)
            if got[0] != "unsure" and same(got) != same(full):
                bad.append(f"{k} without {'/'.join(x for x in gone if (gone[x] is None if isinstance(gone, dict) else 1))}: {got[:2]}, with them {full[:2]}")
    return bad


def main():
    if wrong := top_only():
        print("\n".join(wrong))
        print(f"{len(wrong)} answers made without the page's bottom differ from the answer with it")
        return 1
    got = {k: answer(f) for k, f in CASES.items()}
    got |= {f"on_team: {k}": repr(raidteams.on_team("x", *a[:6], t=TEAMS, iv_sum=(a[6:] or [None])[0])) for k, a in TEAM_CASES.items()}
    got |= {"on_team: no count": repr(raidteams.on_team(None, ["RHYHORN_NORMAL"], False, 2000, 150))}
    got = json.loads(json.dumps(got))  # (tuples -> lists, as the file has them)
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
