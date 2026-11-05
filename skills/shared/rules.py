#!/usr/bin/env python3
"""Tag names, rule numbers and species lists that skills and verdict.py (the rule book) use: one copy, here.
Imports nothing from the skills."""
import re

CLEAN, TRANSFER, EVO = "Clean Trades", "Transfer", "Evo"
# evolve free once traded: Kadabra, Machoke, Graveler (Alolan too), Haunter, Boldore, Gurdurr, Karrablast, Shelmet,
# Phantump, Pumpkaboo. Not the base forms (Abra...). Dex numbers:
# the names make a search too long for the bar to read back
TRADE_EVOS = "64,67,75,93,525,533,588,616,708,710"
EVO_FOR = "CyrillJan"  # the account that wants the XP: HashTagAJay transfers them like the rest
NAMES = {"xxs": "xxs"}  # search term -> nickname, as ivc.make_name spells them. An XXL one is kept instead: XXL_OFF
# an XXL one, traded or not, isn't traded (it has value in showcases, the user 2026-11-04): a favorite, these come off
XXL_OFF = ("GuaranteedLucky", "Old", "GIV", "XLX", "2XL", "Reroll", "Special", "Luckydex", TRANSFER, "IVC")

ALWAYS_KEEP = 44  # IV sum of 98%: 98% and 100% (a shadow: once purified) never get traded or transferred

GIVER, TAKER = "CyrillJan", "HashTagAJay"  # Tradeable is the giver's; the taker's dex, candy and XL decide
TAGS = ["Luckydex", "Reroll", "GIV"]  # by species, in this order
XLX = "XLX"
LUCKY_CANDY = 348  # under this, a lucky one of the family wants a new copy's candy
XL_CAP = 360
UNDER_360_XL = f"&countcandyxl0-{XL_CAP - 1}"  # a count term eats what follows it: always last
XLX_LEVEL = 26  # from here a power-up costs 4 Candy or more (4,000 Stardust at 26-26.5, 4,500+ after)
# CyrillJan's pile only: GIV where it would get Transfer (tagged after XLX, like the evolved GIV ones)
GIV_FOR_TAKER = {"tandemaus": "HashTagAJay still wants the family of 3 Maushold (and CyrillJan gets candy from the "
                              "trade if it ever wants one)"}
XLX_FOR = {TAKER: XLX_LEVEL, GIVER: 29}  # by who'd get it. CyrillJan: 5,000 Stardust+, likely to drop a Candy XL
PVE_TOP = 6  # verdict.py's "raid" list: a traded copy would be this high against some raid boss in DialgaDex
GIVER_MARGIN = 0.15  # CyrillJan's side (giver_species): GIV if a traded copy gets into one of CyrillJan's teams, or
# comes within this much of the #6's rating (a move or stat buff away). Further behind on every boss: outclassed
PVP_FLOOR = 5  # every rank 1 IV at least this
HARD_CANDY = 100  # a stage 1 that costs this much candy to evolve into counts for the evolved GIV rule
BABIES = {172, 173, 174, 175, 236, 238, 239, 240, 298, 360, 406, 433, 438, 439, 440, 446, 447, 458, 848}  # not a stage
SPECIAL = ("legendary", "mythical", "ultrabeast")  # special trades by species: traded by hand, never tagged
# every special trade: no search in tradeable.py tags or powers one up. (Not in the taker's dex is one too: the user
# checks that)
NO_SPECIAL = "&!gigantamax&!shiny&!xxl" + "".join(f"&!{t}" for t in SPECIAL)  # (xxl: kept, tradeable.keep_xxl_ones)
DYNAMAX = "&dynamax&!traded"  # evolved GIV too
OLD, OLD_AGE = "Old", "&age300-"  # caught 300+ days ago: after Luckydex, before Reroll, GIV and XLX (verdict.py)
# verdict.py, HashTagAJay only, after Old: medal ones (by weight, read on the detail page) -> GIV, for any other account.
# The Youngster medal counts tiny Rattata (any region), the Fisherman medal big Magikarp
MEDALS = [("Rattata", "&19&xxs,xs", lambda kg: kg <= 2.41), ("Magikarp", "&129", lambda kg: kg >= 13.13)]
MEDAL_KG = {"Rattata": (0.5, 10), "Magikarp": (2, 30)}  # a weight outside this is a misread (a lost decimal point)


def xxl_off(tags):
    """which of XXL_OFF these tags, as read, hold (letters only: the page's reader drops digits, so 2XL reads as XL)"""
    key = lambda s: re.sub(r"[^A-Z]", "", s.upper())
    have = {key(t) for t in tags}
    return tuple(t for t in XXL_OFF if key(t) in have)
