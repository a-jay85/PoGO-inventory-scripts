#!/usr/bin/env python3
"""Tag names and rule constants that skills and ../shared/verdict.py both need: one copy, here."""
import re

CLEAN, TRANSFER, EVO = "Clean Trades", "Transfer", "Evo"
# evolve free once traded: Kadabra, Machoke, Graveler (Alolan too), Haunter, Boldore, Gurdurr, Karrablast, Shelmet,
# Phantump, Pumpkaboo. Not the base forms (Abra...). Dex numbers:
# the names make a search too long for the bar to read back
TRADE_EVOS = "64,67,75,93,525,533,588,616,708,710"
EVO_FOR = "CyrillJan"  # the account that wants the XP: HashTagAJay transfers them like the rest
NAMES = {"xxs": "xxs"}  # search term -> nickname, as ivc.make_name spells them. An XXL one is kept instead: XXL_OFF
# an XXL one, traded or not, isn't traded (it has value in showcases, the user 2026-11-04): a favorite, these come off
XXL_OFF = ("GuaranteedLucky", "Old", "GIV", "XLX", "2XL", "Reroll", "Special", "Luckydex", TRANSFER)


def xxl_off(tags):
    """which of XXL_OFF these tags, as read, hold (letters only: the page's reader drops digits, so 2XL reads as XL)"""
    key = lambda s: re.sub(r"[^A-Z]", "", s.upper())
    have = {key(t) for t in tags}
    return tuple(t for t in XXL_OFF if key(t) in have)
