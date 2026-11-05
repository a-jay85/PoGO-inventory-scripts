#!/usr/bin/env python3
"""Tag names and rule constants that skills and ../shared/verdict.py both need: one copy, here."""

CLEAN, TRANSFER, EVO = "Clean Trades", "Transfer", "Evo"
# evolve free once traded: Kadabra, Machoke, Graveler (Alolan too), Haunter, Boldore, Gurdurr, Karrablast, Shelmet,
# Phantump, Pumpkaboo. Not the base forms (Abra...). Dex numbers:
# the names make a search too long for the bar to read back
TRADE_EVOS = "64,67,75,93,525,533,588,616,708,710"
EVO_FOR = "CyrillJan"  # the account that wants the XP: HashTagAJay transfers them like the rest
NAMES = {"xxl": "XXL", "xxs": "xxs"}  # search term -> nickname, as ivc.make_name spells them
