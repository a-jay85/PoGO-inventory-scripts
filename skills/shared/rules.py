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
# every family with an evolution that costs over 100 candy (Magikarp 400, Snom 400, Roggenrola 200, ...), from
# tradeable.py refresh's giv-evolved file (2026-10-29) and the family tree. Special trades left out (never Transfer).
# An untraded one gets GIV where it would get Transfer (the user, 2026-11-12), except a trade evolution on EVO_FOR,
# or when its holder has COSTLY_ENOUGH Candy of the family (the user, 2026-11-25: the trade is for the sender's candy)
COSTLY_LINES = ("129,130,320,321,333,334,524,525,526,532,533,534,588,589,616,617,636,637,708,709,710,711,714,715,"
                "759,760,767,768,840,841,842,848,849,854,855,872,873,1011,1012,1013,1019")
COSTLY_ENOUGH = 5000  # a costly line's holder with this much Candy of it needs no trade's candy (Magikarp)
NAMES = {"xxs": "xxs"}  # search term -> nickname, as ivc.make_name spells them. An XXL one is kept instead: XXL_OFF
# an XXL one, traded or not, isn't traded (it has value in showcases, the user 2026-11-04): a favorite, these come off
XXL_OFF = ("GuaranteedLucky", "Old", "GIV", "XLX", "2XL", "Reroll", "Special", "Luckydex", TRANSFER, "IVC")
# one on its holder's own raid team (roster/raidteam.py keep): a favorite, these come off. The user's own Old and
# GuaranteedLucky stay (verdict.py: the user's own tags come before the raid team rule)
RAID_OFF = tuple(t for t in XXL_OFF if t not in ("GuaranteedLucky", "Old"))

ALWAYS_KEEP = 44  # IV sum of 98%: 98% and 100% (a shadow: once purified) never get traded or transferred

GIVER, TAKER = "CyrillJan", "HashTagAJay"  # Tradeable is the giver's; the taker's dex, candy and XL decide
TAGS = ["Luckydex", "Reroll", "GIV"]  # by species, in this order
XLX = "GIV"  # the tag a level 26+ one gets (XLX_LEVEL). It was its own tag, XLX, till the user folded it into GIV
OLD_XLX = "XLX"  # (2026-11-19): every #XLX was retagged GIV on both phones. Still taken off wherever it shows up
LUCKY_CANDY = 348  # under this, a lucky one of the family wants a new copy's candy
XL_CAP = 360
TEAM_SLOTS = 5  # a Team Future or Team Ideal (roster.ideal_firsts) holds 5 of a boss's #1 non-mega attacker.
# CyrillJan's GIV bar for that line: XL_CAP for each of its 100s, up to TEAM_SLOTS (the user, 2026-11-23: tradeable.team_xl_need)
DMAX_CANDY = 1000  # one that can Dynamax (not a Dynamax one): GIV while its account has this much Candy or less, or
# XL_CAP + what one Max Move costs in Candy XL or less (the user, 2026-11-16; one, not three: 2026-11-19; 1,000 Candy, was 2,500: 2026-11-20). Over both: no rule wants it
UNDER_360_XL = f"&countcandyxl0-{XL_CAP - 1}"  # (a count term can sit anywhere: tried 2026-11-23, SEARCH.md)
UNDER_348_CANDY = f"&countcandy0-{LUCKY_CANDY - 1}"
# What the account that trades a Pokémon away gets, of that Pokémon's family (the user, 2026-11-23). A transfer gives
# only TRANSFER_CANDY, so a trade always pays the sender more. CyrillJan's GIV bar (verdict.cyrill_short) is built on it
TRADE_SENDER_CANDY = {(0, 10): 2, (10, 100): 3, (100, None): 4}  # km between the two traded Pokémon's catch places
TRADE_SENDER_XL = 1  # 2 on a Friendship Friday (the 2XL tag)
TRANSFER_CANDY = 1
XLX_LEVEL = 26  # from here a power-up costs 4 Candy or more (4,000 Stardust at 26-26.5, 4,500+ after)
# CyrillJan's pile only: Reroll, with the other reasons HashTagAJay needs one (GIV till 2026-11-23, when GIV became
# "CyrillJan needs the trade's candy" and Reroll "HashTagAJay needs it": the user)
REROLL_FOR_TAKER = {"TANDEMAUS_NORMAL": "HashTagAJay still wants the family of 3 Maushold"}
XLX_FOR = {TAKER: XLX_LEVEL, GIVER: XLX_LEVEL}  # by who'd get it: 4 Candy+ a power-up, both (the user, 2026-11-16)
PVE_TOP = 6  # verdict.py's "raid" list: a traded copy would be this high against some raid boss in DialgaDex
# HashTagAJay's pile (Leftovers), judged for CyrillJan or the user's wife's account, which is behind CyrillJan: "good
# for any account" (the user, 2026-11-16). hashtag_species() in tradeable.py
REROLL_ENOUGH = 5  # CyrillJan's Reroll: HashTagAJay holding this many 100s of a family needs no more (the user, 2026-11-20)
REROLL_ML = 20  # Reroll: PvPoke's Master League top this many (or evolves into one)
HARD_EGGS = ("10 km", "12 km")  # GIV: a family that hatches from these eggs (refresh keeps every one it has seen)
HARD_TO_FARM = ("SMEARGLE_NORMAL",)  # GIV: hard to farm too
# Leftovers: a likely special trade the user tags by hand (the user, 2026-11-16). PvPoke's "regional" tag, plus these
# it misses, and their earlier stages. Spinda: each pattern is a new dex entry. Not SF_NATIVE
BY_HAND = ("SPINDA_00", "SAWK_NORMAL", "SCATTERBUG_ARCHIPELAGO", "SPEWPA_ARCHIPELAGO", "VIVILLON_ARCHIPELAGO", "FLABEBE_BLUE", "FLOETTE_BLUE", "FLORGES_BLUE",
           "ORICORIO_BAILE", "ORICORIO_PAU", "ORICORIO_SENSU", "SHELLOS_EAST_SEA", "GASTRODON_EAST_SEA", "FURFROU_DANDY")
# regionals that spawn in San Francisco, CA: judged like any other, not by hand (the user, 2026-11-19). From Pokemon GO
# Hub's regional list (North America, the Americas, the Western Hemisphere). A form the page can't tell apart (Shellos'
# sea, Basculin's stripe, Flabebe's flower, Tatsugiri, Furfrou's trim, Vivillon's pattern) stays by hand
SF_NATIVE = {"TAUROS_NORMAL", "TAUROS_PALDEA_AQUA", "ILLUMISE_NORMAL", "SEVIPER_NORMAL", "LUNATONE_NORMAL", "PANPOUR_NORMAL", "SIMIPOUR_NORMAL", "THROH_NORMAL", "DURANT_NORMAL",
             "ORICORIO_POMPOM"}
# regional exclusives (each gives the game data's "regional" tag). PokeMiners' game master has no region field, so
# this is a hand list (the user, 2026-11-27): PvPoke's "regional" tag as of 2026-11-27
REGIONAL = ("FARFETCHD_NORMAL", "KANGASKHAN_NORMAL", "KANGASKHAN_NORMAL_MEGA", "MR_MIME_NORMAL", "TAUROS_NORMAL", "TAUROS_PALDEA_AQUA", "TAUROS_PALDEA_BLAZE",
            "TAUROS_PALDEA_COMBAT", "HERACROSS_NORMAL", "HERACROSS_NORMAL_MEGA", "CORSOLA_NORMAL", "VOLBEAT_NORMAL", "ILLUMISE_NORMAL", "TORKOAL_NORMAL", "ZANGOOSE_NORMAL",
            "SEVIPER_NORMAL", "LUNATONE_NORMAL", "SOLROCK_NORMAL", "TROPIUS_NORMAL", "RELICANTH_NORMAL", "PACHIRISU_NORMAL", "GASTRODON_EAST_SEA", "CHATOT_NORMAL", "CARNIVINE_NORMAL",
            "PANSAGE_NORMAL", "SIMISAGE_NORMAL", "PANSEAR_NORMAL", "SIMISEAR_NORMAL", "PANPOUR_NORMAL", "SIMIPOUR_NORMAL", "BASCULIN_BLUE_STRIPED", "MARACTUS_NORMAL", "SIGILYPH_NORMAL",
            "BOUFFALANT_NORMAL", "HEATMOR_NORMAL", "DURANT_NORMAL", "HAWLUCHA_NORMAL", "KLEFKI_NORMAL", "COMFEY_NORMAL", "STONJOURNER_NORMAL", "TATSUGIRI_CURLY",
            "TATSUGIRI_DROOPY", "TATSUGIRI_STRETCHY")
# not in GO yet (the game data's released: false). PokeMiners' game master holds every Pokémon the game knows, out or
# not, so this is a hand list (the user, 2026-11-27): the ones both PvPoke and DialgaDex called unreleased on
# 2026-11-27, plus Koraidon, Miraidon, Type: Null, and forms seen only in battle. Take one out when it comes out
UNRELEASED = (
    "PHIONE_NORMAL", "MANAPHY_NORMAL", "ARCEUS_NORMAL", "ARCEUS_BUG", "ARCEUS_DARK", "ARCEUS_DRAGON", "ARCEUS_ELECTRIC", "ARCEUS_FAIRY",
    "ARCEUS_FIGHTING", "ARCEUS_FIRE", "ARCEUS_FLYING", "ARCEUS_GHOST", "ARCEUS_GRASS", "ARCEUS_GROUND", "ARCEUS_ICE",
    "ARCEUS_POISON", "ARCEUS_PSYCHIC", "ARCEUS_ROCK", "ARCEUS_STEEL", "ARCEUS_WATER", "DARMANITAN_GALARIAN_ZEN",
    "DARMANITAN_ZEN", "MELOETTA_PIROUETTE", "WISHIWASHI_SOLO", "WISHIWASHI_SCHOOL", "PYUKUMUKU_NORMAL",
    "TYPE_NULL_NORMAL", "SILVALLY_NORMAL", "SILVALLY_BUG", "SILVALLY_DARK", "SILVALLY_DRAGON", "SILVALLY_ELECTRIC", "SILVALLY_FAIRY",
    "SILVALLY_FIGHTING", "SILVALLY_FIRE", "SILVALLY_FLYING", "SILVALLY_GHOST", "SILVALLY_GRASS", "SILVALLY_GROUND",
    "SILVALLY_ICE", "SILVALLY_POISON", "SILVALLY_PSYCHIC", "SILVALLY_ROCK", "SILVALLY_STEEL", "SILVALLY_WATER",
    "MINIOR_BLUE", "NECROZMA_ULTRA", "MAGEARNA_NORMAL", "CHEWTLE_NORMAL", "DREDNAW_NORMAL", "MILCERY_NORMAL", "ALCREMIE_NORMAL", "PINCURCHIN_NORMAL", "EISCUE_ICE", "EISCUE_NOICE",
    "CUFANT_NORMAL", "COPPERAJAH_NORMAL", "DRACOZOLT_NORMAL", "ARCTOZOLT_NORMAL", "DRACOVISH_NORMAL", "ARCTOVISH_NORMAL",
    "ETERNATUS_ETERNAMAX", "GLASTRIER_NORMAL", "SPECTRIER_NORMAL", "CALYREX_NORMAL", "CALYREX_ICE_RIDER", "CAPSAKID_NORMAL", "SCOVILLAIN_NORMAL", "RELLOR_NORMAL",
    "RABSCA_NORMAL", "FINIZEN_NORMAL", "PALAFIN_ZERO", "PALAFIN_HERO", "CYCLIZAR_NORMAL", "VELUZA_NORMAL", "FARIGIRAF_NORMAL", "GREATTUSK_NORMAL",
    "SCREAMTAIL_NORMAL", "BRUTEBONNET_NORMAL", "FLUTTERMANE_NORMAL", "SLITHERWING_NORMAL", "SANDYSHOCKS_NORMAL", "IRONTREADS_NORMAL", "IRONBUNDLE_NORMAL", "IRONHANDS_NORMAL",
    "IRONJUGULIS_NORMAL", "IRONMOTH_NORMAL", "IRONTHORNS_NORMAL", "WOCHIEN_NORMAL", "CHIENPAO_NORMAL", "TINGLU_NORMAL", "CHIYU_NORMAL", "ROARINGMOON_NORMAL",
    "IRONVALIANT_NORMAL", "WALKINGWAKE_NORMAL", "IRONLEAVES_NORMAL", "OKIDOGI_NORMAL", "MUNKIDORI_NORMAL", "FEZANDIPITI_NORMAL", "ARCHALUDON_NORMAL", "GOUGINGFIRE_NORMAL",
    "RAGINGBOLT_NORMAL", "IRONBOULDER_NORMAL", "IRONCROWN_NORMAL", "TERAPAGOS_NORMAL", "PECHARUNT_NORMAL", "KORAIDON_APEX", "MIRAIDON_ULTIMATE",
    # seen only in battle: none is ever in a storage
    "AEGISLASH_BLADE", "MIMIKYU_BUSTED", "MORPEKO_HANGRY", "CRAMORANT_GULPING", "CRAMORANT_GORGING")
PVP_FLOOR = 5  # every rank 1 IV at least this
HARD_CANDY = 100  # a stage 1 that costs this much candy to evolve into counts for the evolved GIV rule
# dex numbers whose shiny the game hasn't released: one is never shiny, whatever the read says (Minior, the user
# 2026-11-22: its shiny icon read failed and left one unsure)
NO_SHINY = {774}
BABIES = {172, 173, 174, 175, 236, 238, 239, 240, 298, 360, 406, 433, 438, 439, 440, 446, 447, 458, 848}  # not a stage
SPECIAL = ("legendary", "mythical", "ultrabeast")  # special trades by species: traded by hand, never tagged
# every special trade: no search in tradeable.py tags or powers one up. (Not in the taker's dex is one too: the user
# checks that)
NO_SPECIAL = "&!gigantamax&!shiny&!xxl" + "".join(f"&!{t}" for t in SPECIAL)  # (xxl: kept, tradeable.keep_xxl_ones)
DYNAMAX = "&dynamax&!traded"  # evolved GIV too
NEVER_TRADE = "&!#&!favorite&!traded&!shadow&!shiny&!XXL&!4*&!3*&"  # the user's: Luckydex never trades these
OLD, OLD_AGE = "Old", "&age300-"  # caught 300+ days ago: after Luckydex, before Reroll and GIV (verdict.py)
# verdict.py, HashTagAJay only, after Old: medal ones (by weight, read on the detail page) -> GIV, for any other account.
# The Youngster medal counts tiny Rattata (any region), the Fisherman medal big Magikarp
MEDALS = [("Rattata", "&19&xxs,xs", lambda kg: kg <= 2.41), ("Magikarp", "&129", lambda kg: kg >= 13.13)]
MEDAL_KG = {"Rattata": (0.5, 10), "Magikarp": (2, 30)}  # a weight outside this is a misread (a lost decimal point)

# the bulk taggers (tradeable.py tag, cleantrades.py) only tag what's sure to get that same tag from verdict.py. These
# have rules of their own there, so they stay out of a tag search and go through the door one by one
GYM_DEX = (113, 143, 202, 242, 289, 977)  # ivc.GYM_DEFENDERS: the gym rule needs its top 20
ODD = ("lucky", "costume", "background")
TAG_SKIP = "".join(f"&!{t}" for t in (*ODD, *GYM_DEX))  # NO_SPECIAL leaves out the others
BULK_GUARD = NO_SPECIAL + TAG_SKIP
DOOR_PICK = "&!xxl&" + ",".join(map(str, ("shiny", "gigantamax", *SPECIAL, *ODD, *GYM_DEX)))  # all but xxl: BULK_GUARD's
NEVER_TRADED = {999, 1000}  # Gimmighoul, Gholdengo: can't be traded, so never lucky
LUCKY_YEARS = (2016, 2020)  # an untraded catch from these years is lucky once traded
GUARANTEED = "GuaranteedLucky"
LUCKY_YEAR = f"&year{LUCKY_YEARS[0]}-{LUCKY_YEARS[1]}"

# the terms each saved search on the phone must hold for the scripts to be right. Its other terms are the user's.
# savedsearches.py reads them off the phone. (): it only has to exist
SAVED = {GIVER: {CLEAN: ("traded", "!3*", "!4*", "!favorite", "!#"),
                 "Tradeable": ("!traded", "!3*", "!4*", "!favorite", "!shadow", "!#"),
                 "IV Check": ("4*,3*", "!favorite", "!#")},
         TAKER: {CLEAN: ("traded", "!3*", "!4*", "!favorite", "!#"),
                 "IV Check": ("4*,3*", "!favorite", "!#"),
                 "PvpC1": (), "PvpC2": (),
                 "Leftovers": ("!favorite", "!mythical", "!gigantamax", "!#", "age0-7")}}  # (leftovers.py: any tag or
# star takes one out of it. No mythical or Gigantamax: the door types no mythical&raid search, the walk adds nothing,
# 2026-11-19. age0-7, this week's catches (the user, 2026-11-26): the door splits it by traded only, all new)



def held(tags, among):
    """which of among these tags, as read, hold (letters only: the page's reader drops digits, so 2XL reads as XL)"""
    key = lambda s: re.sub(r"[^A-Z]", "", s.upper())
    have = {key(t) for t in tags}
    return tuple(t for t in among if key(t) in have)


def xxl_off(tags):
    return held(tags, XXL_OFF)
