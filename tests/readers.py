#!/usr/bin/env python3
"""Pins what every text reader says today: the search-bar checks, the result counts and the name matchers.
They take OCR text and give an answer, no phone. A refactor that merges or moves one must give the same answers.

  python3 tests/readers.py            check every reader against tests/readers.json
  python3 tests/readers.py --record   write readers.json from today's code (after a change you meant)

The cases are the real misreads from the run logs, plus the kinds of misread the code's comments name: the
magnifier glued on in front, a long search cut off at one end, a '!' lost or read as 'l', a '&' read as '8'.
Search strings and made-up names only: the repo is public.
"""
import importlib.util, json, os, sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
GOLD = os.path.join(ROOT, "tests", "readers.json")
os.environ.pop("POGO_PHONE", None)  # the iPhone path: every reader stays on the text it's given (no screenshot)
for d in ("shared", "cleanup", "dex", "trade", "gift", "mega", "ivc"):
    sys.path.append(os.path.join(SKILLS, d))

import base, search, ui  # noqa: E402
import tagsheet, savedsearch, dex, trade, gift, mega  # noqa: E402


def by_path(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SKILLS, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ivc_names = by_path("ivcnames", "ivc/names.py")
ivc_run = by_path("ivc_run", "ivc/run.py")
assert not ui.ANDROID

# ---------- cases ----------

REAL = [  # (bar read, search typed): straight from the run logs
    (",lucky&320&!costume", "lucky&320&!costume"),
    ("#Nope&shadow&!shiny&!costume&!", "#Nope&shadow&!shiny&!costume&!xxl&!xxs"),
    ("1-26,172&countcandyx|360-", "1-26,172&countcandyxl360-"),
    ("144&3*,*,4*&!galar", "144&3*,4*&!galar"),
    ("150&3*,4*&@flamethrower,@focus", "150&3*,4*&@flamethrower,@focus blast,@hyper beam,@ice beam,@psycho cut,"
                                         "@shadow ball,@thunderbolt"),
    ("483*,", "4&3*,4*&shadow"),
    ("530&3**,4*&shadowx", "530&3*,4*&shadow"),
    ("giv,xl&distanceo-1i0&conntcandy", "giv,xlx&distance0-100&countcandy0-2499"),
]

QUERIES = [q for _, q in REAL] + [
    "#Nope&!shadow&4attack,4defense&4attack,4hp&4defense,4hp",
    "#Nope&shadow&3*,4*",
    "#Nope&!traded&!shiny&!costume&legendary",
    "#Nope&!traded&!shiny&!costume&793-806,808,809",
    "#Nope&purified",
    "#Transfer,#Nope&!traded&xxl",
    "&!#&!favorite&!traded&!shadow&!shiny&!XXL&!4*&!3*&",
    "giv,xlx&distance100-&countcandy0-2499",
    "giv,xlx&distance0-100&countcandy2500-",
    "1-151&countcandyxl0-359",
    "PvpC",
]


def nth(s, ch, new, n=0):
    """s with its n-th ch swapped for new (s itself if there's none)"""
    i = -1
    for _ in range(n + 1):
        i = s.find(ch, i + 1)
        if i < 0:
            return s
    return s[:i] + new + s[i + 1:]


def digit_amp_8(s):
    return "".join("8" if c == "&" and i and s[i - 1].isdigit() else c for i, c in enumerate(s))


def variants(q):
    """the misreads the code's comments name"""
    flat = q.replace(" ", "")
    out = [q, flat, "Q" + flat, "9" + flat, "<" + flat, "," + flat, flat + "x", flat.upper(),
           nth(flat, "!", ""), nth(flat, "!", "l"), nth(flat, "!", "|"), nth(flat, "!", "."), nth(flat, "!", "", 1),
           digit_amp_8(flat), flat.replace("&", "8"), flat.replace("0", "o"), flat.replace("l", "1"),
           flat.replace("*", '"'), flat.replace("-", ""),
           flat[:28], flat[:20], flat[-20:], flat[-28:], "Q" + flat[:28], nth(flat[:28], "!", ""),
           nth(flat[-20:], "!", "I"), flat[:-1], flat[1:], ""]
    return list(dict.fromkeys(out))  # (in order, no repeats)


PAIRS = list(dict.fromkeys(REAL + [(g, q) for q in QUERIES for g in variants(q)]))
WRONG = [(QUERIES[i], QUERIES[i + 1]) for i in range(len(QUERIES) - 1)]  # another search left in the bar
PAIRS += [p for p in WRONG if p not in PAIRS]

NAMES = [  # (read, wanted)
    ("PvpL Medi", "PvpL Medi"), ("PypL Medi", "PvpL Medi"), ("PУpL Medi", "PvpL Medi"), ("PvPL Medi", "PvpL Medi"),
    ("PvpL Medi ", "PvpL Medi"), ("PvpL Medl", "PvpL Medi"), ("PvpGU 1Eaf", "PvpGU lEaf"), ("PvpGU IEaf", "PvpGU lEaf"),
    ("PvpL Med", "PvpL Medi"), ("Pvp Medi", "PvpL Medi"), ("XvpL Medi", "PvpL Medi"),
    ("40 a", "40 a"), ("40 al", "40 a"), ("40 aI", "40 a"), ("40 ax", "40 a"), ("84/9", "84/9"), ("849", "84/9"),
    ("xXS 96", "XXS 96"), ("96^", "96"), ("96*", "96"), ('96"', "96*"), ("96|", "96"), ("96…", "96"), ("9", "96"),
    ("", ""), ("", "96"), ("lyc60", "lycбo"), ("lycбo", "lycbo"), ("Fr1endly", "Friendly"), ("Frlendly", "Friendly"),
    ("Frien", "Friendly"), ("Ab&c", "Ab8c"), ("Abcd", "Abxy"), (None, "PvpL Medi"),
]

ONE = sorted({g for g, _ in PAIRS} | {q for _, q in PAIRS} | {"PvpC1", "PvpCl", "Clean Trades", "CleanTrades",
                                                               "xix", "countcandyx10-359", "!x", "a:b"})


def texts(*lines):
    """OCR boxes (x, y, w, h, text) at these heights"""
    return [(0.3, y, 0.4, 0.03, s) for y, s in lines]


COUNTS = {
    "Q (7)": texts((0.12, "Q (7)")),
    "9 (1,234)": texts((0.12, "9 (1,234)")),
    "(12)": texts((0.12, "(12)")),
    "(O)": texts((0.12, "(O)")),
    "(0)": texts((0.12, "(0)")),
    "too low": texts((0.16, "Q (7)")),
    "between": texts((0.145, "Q (7)")),
    "words": texts((0.12, "POKEMON (7)")),
    "none": texts((0.5, "CP 1234")),
    "two": texts((0.12, "Q (3)"), (0.13, "(9)")),
}

TITLE, CANCEL = (0.3842, 0.382, 0.2315, 0.0157, "Set Nickname"), (0.4235, 0.611, 0.153, 0.0185, "CANCEL")
OK = (0.468, 0.5416, 0.064, 0.0157, "OK")
RENAMES = {  # the Set Nickname dialog's OCR boxes, from run captures
    "OK read": [TITLE, (0.1625, 0.4493, 0.1726, 0.0228, "Pvp U87"), OK, CANCEL],
    "OK not read": [TITLE, (0.1625, 0.4493, 0.1726, 0.0228, "Pvp U87"), CANCEL],  # Ralts 2026-10-25
    "empty, OK not read": [TITLE, CANCEL],
    "item behind it": [TITLE, (0.6798, 0.4112, 0.1823, 0.0135, "GREAT BALL"),
                       (0.1576, 0.4494, 0.0985, 0.018, "87 A"), (0.798, 0.4899, 0.069, 0.0112, "GIFT"), OK, CANCEL],
    "no CANCEL either": [TITLE, (0.1625, 0.4493, 0.1726, 0.0228, "Pvp U87")],
}

SHEETS = {  # the Mega level page and the Mega Evolve box, from the Pixel 2026-10-26 (rows as OCR read them)
    "base, 2 more": texts((0.27, "6 Days 2 Hours"), (0.30, "REST PERIOD"), (0.33, "100's Mega Level"),
                          (0.38, "Base Level"), (0.54, "To Reach High Level:"),
                          (0.57, "Mega Evolve Manectric 2 more times."), (0.62, "MEGA EVOLVE"), (0.78, "LEVEL UP")),
    "high, 13 more": texts((0.33, "100's Mega Level"), (0.39, "High Level"), (0.53, "To Reach Max Level:"),
                           (0.57, "Mega Evolve Camerupt 13 more times."), (0.62, "MEGA EVOLVE")),
    "high, 1 more": texts((0.33, "100's Mega Level"), (0.39, "High Level"),
                          (0.57, "Mega Evolve Camerupt 1 more time."), (0.62, "MEGA EVOLVE")),
    "done today": texts((0.33, "100's Mega Level"), (0.38, "Base Level"),
                        (0.57, "Mega Evolve Manectric 1 more time."),
                        (0.61, "Daily level limit met. You can make additional progress"), (0.63, "tomorrow.")),
    "mega now": texts((0.27, "07:59:23"), (0.30, "REMAINING MEGA EVOLUTION PERIOD"), (0.33, "100's Mega Level"),
                      (0.38, "Base Level")),
    "max": texts((0.27, "100's Mega Level"), (0.32, "MEGA RAICHU X"), (0.40, "Max Level"),
                 (0.55, "To Reach Super Max Level:"), (0.63, "LEVEL UP")),
    "detail page": texts((0.5, "CP 1234"), (0.6, "MEGA EVOLVE")),
}
SHEETS["base, 2 more"].append((0.75, 0.615, 0.06, 0.02, "• 18"))  # the cost, right of the button
SHEETS["high, 13 more"].append((0.75, 0.615, 0.06, 0.02, "17"))
ASKS = {
    "x18": texts((0.32, "Do you want to Mega Evolve 100?"), (0.43, "x18"), (0.66, "YES"), (0.72, "NO")),
    "no cost": texts((0.32, "Do you want to Mega Evolve 100?"), (0.66, "YES"), (0.72, "NO")),
    "x7,500": texts((0.32, "Do you want to Mega Evolve 100?"), (0.43, "x7,500")),
    "not the box": texts((0.39, "Do you really want to Mega"), (0.48, "Your 100 will no longer be Mega Evolved!")),
}
BANNERS = {  # OCR from run captures: the banner over the ME tab, and the same words as Friends tab rows
    "over the ME tab": texts((0.04, "10:00"), (0.12, "playhardererer sent you a Gift!"), (0.18, "CyrillJan"),
                             (0.59, "LEVEL")),
    "two lines": texts((0.11, "EXGunstarHero sent you a"), (0.14, "Gift!"), (0.19, "CyrillJan")),
    "opened": texts((0.10, "RINRINRINSORA and 10 other"), (0.13, "friends have opened your"), (0.16, "Gifts!")),
    "friend rows": texts((0.09, "ME"), (0.09, "FRIENDS"), (0.09, "SOCIAL"), (0.31, "1738Sanmiggz"),
                         (0.36, "1738Sanmiggz sent you a"), (0.38, "Gift!"), (0.52, "1D13GOD sent you a Gift!")),
    "the list": texts((0.18, "Q Search"), (0.3, "CP 1234")),
}
GIFTS = [("Mission Walk", "San Francisco, California,"), ("Mission Walk", "San Francisco, CA, United"), ("Mural", "Chicago, IL, United States"),
         ("Hydrant", "Raleigh, NC, United"), ("Mural", "Fremont, CA, United"), ("Mural", "Fremont, California,"), ("Mural", "Fremont, Califomia,"),
         ("Park", "Reno, NV, United"), ("Park", "Toronto, Canada"), ("Park", "Charlotte, North Carolina,"), ("Sea Lion", "San Francisco, CA, United"),
         ("Sea Lion", "Oakland, CA, United"), ("Tree", "Oakland, California,"), ("Mission Rock", "San Francisco, CA, United"), ("Rocky", "Fremont, CA, United"),
         ("Olive My Love, Olive My Heart", "San Francisco, CA, United"), ("Mural", "California"), ("Mural", "")]
NICKS = ["98 AD C* X", "93 D PsyS* Y", "GGB X", "Mewtwo", "100", "OpenGiftOnCD", "Max", "X", ""]
BADGES = {k: texts((0.69, v)) for k, v in {"days": "5 DAYS", "1 day": "1 DAY", "left": "07:59 left",
                                           "none": "WEIGHT", "hours": "6 HOURS"}.items()}

# ---------- readers ----------


def strict(got, q):
    tagsheet._views.clear()
    return [tagsheet.strict(got, q), list(map(list, tagsheet._views))]


def in_bar(phone):
    def f(got, q):
        p = SimpleNamespace(name=phone, texts=texts((0.1, got)))
        return trade.in_bar(p, q)
    return f


PAIRED = {
    "search.same_query": search.same_query,
    "search.bar_shows": search.bar_shows,
    "search.amp_as_8": search.amp_as_8,
    "tagsheet.bar_whole": lambda g, q: tagsheet.bar_whole(g.replace(" ", ""), q),
    "search.bar_read": lambda g, q: search.bar_read(texts((0.1, g))),
    "trades.strict": strict,
    "trade.in_bar ios": in_bar("ios"),
    "trade.in_bar android": in_bar("android"),
}
SINGLE = {
    "trade.same_l": trade.same_l,
    "trade.pile": trade.pile,
    "cleantrades.same_l": savedsearch.same_l,
    "cleantrades.key": savedsearch.key,
    "run.short": base.short,
    "ivc.short": ivc_run.short,
}
NAMED = {
    "run.same_name": base.same_name,
    "names.same_name": ivc_names.same_name,
    "ivc.same_name": ivc_run.same_name,
    "gift.same_name": gift.same_name,
}
COUNTERS = {
    "search.result_count": search.result_count,
    "trade.results": lambda ts: trade.results(SimpleNamespace(texts=ts)),
}
DIALOGS = {
    "ui.nickname_field": lambda ts: ui.nickname_field(ts)[4],
    "ui.dialog_ok": lambda ts: (lambda b: b and round(b[1], 4))(ui.dialog_ok(ts)),
}


def box(x, y, s):
    return (x, y, 0.1, 0.02, s)


LISTS = {  # the list's tiles: normal ones count once, and a list of only shinies has no real CP to go by
    "plain": [box(.15, .3, "CP2554"), box(.45, .3, "CP 300"), box(.15, .4, "96 HA"), box(.45, .4, "Zubat")],
    "a shiny by a plain one": [box(.15, .3, "CP2554"), box(.45, .3, "2168"), box(.15, .4, "96 HA"), box(.45, .4, "Zubat")],
    "only shinies, from the Pixel 2026-11-03": [box(.15, .3, "2554"), box(.45, .3, "1283"), box(.15, .4, "80 def"),
                                               box(.45, .4, "• Gardevoir"), box(.15, .5, "€2050,"), box(.15, .6, "• Kartana")],
    "shiny labels": [box(.15, .3, "c2554,"), box(.45, .3, "-2050"), box(.15, .4, "80 def"), box(.45, .4, "• Kartana")],
    "a number with no name": [box(.15, .3, "2554"), box(.8, .1, "9/12")],
}


SCREENS = {  # the map's friend row must not read as the list's search bar: the Pixel 2026-11-03
    "map, friend row": [box(.06, .038, "11:17"), box(.23, .133, "Me"), box(.23, .155, "10"), box(.46, .133, "CPD"),
                        box(.69, .133, "HashT..."), box(.44, .2, "NEW!"), box(.02, .962, "CyrilJan")],
    "typed number, tabs showing": [box(.1, .079, "TAGS"), box(.45, .079, "POKÉMON"), box(.8, .079, "EGGS"), box(.23, .17, "113")],
    "typed number and letters, no tabs": [box(.23, .17, "113&shadow")],
    "weekly challenge progress box": [box(.31, .196, "WEEKLY CHALLENGE"), box(.2, .3, "Catch 500 Pokémon"),
                                      box(.2, .33, "387 / 500"), box(.4, .8, "LET'S GO!")],
    "a party's summary": [box(.2, .14, "Total KM Explored"), box(.4, .21, "1.3 km"), box(.1, .18, "Me & HashTagAJay"), box(.4, .64, "SHARE")],
}

_LIST = [box(.1, .079, "TAGS"), box(.8, .079, "EGGS"), box(.23, .17, "Search")] + [box(.1 + i / 20, .3, f"CP {i}00") for i in range(1, 7)] + \
        [box(.1, .4 + i / 50, n) for i, n in enumerate(("Bulbasaur", "Ivysaur", "Pidgey", "Rattata", "Zubat", "Geodude"))]
_POPUP = [box(.1, .4, "Your party completed"), box(.1, .5, "Claim your reward"), box(.4, .8, "CLAIM REWARD"), box(.1, .6, "Spin stops")]
CHANGES = {  # (before a pause, after it): another screen, or the same one?
    "the same": (_LIST, _LIST),
    "one word misread": (_LIST, _LIST[:-1] + [box(.1, .5, "Geodudee")]),
    "another number": (_LIST, _LIST[:3] + [box(.1, .3, "CP 999")] + _LIST[4:]),
    "a popup over it": (_LIST, _LIST + _POPUP),
    "two unknown screens": (_POPUP, _LIST[-6:]),
    "the screen can't be seen": (_LIST, None),
}


def row_of(y, *tiles):
    return [(.17 + i * .32, y, cp) for i, (_, cp) in enumerate(tiles)], [(n, cp, .17 + i * .32, y + .065) for i, (n, cp) in enumerate(tiles)]


def screen(top, *rows):
    made = [row_of(top + i * .165, *r) for i, r in enumerate(rows)]
    return [c for m in made for c in m[0]], [t for m in made for t in m[1]]


def places(screens):
    grid = []
    for cps, tiles in screens:
        search.add_to_grid(grid, search.screen_rows(cps, tiles))
    return search.grid_tiles(grid)


_A, _B, _C, _D = [("96 HA", 398), ("Pikachu", 379), ("Pikachu", 384)], [("Pikachu", 379), ("Pichu", 255), ("Lego", 512)], \
    [("Pikachu", 121), ("Pikachu", 379), ("Pichu", 90)], [("Pikachu", 379), ("Pikachu", 200), ("Lego", 77)]
_TWIN = [("Pikachu", 379)] * 3
GRIDS = {  # what full reads make of made-up screens. The answer is used only when its count is the game's
    "twins on two screens stay two": [screen(.3, _A, _B), screen(.3, _B, _C), screen(.3, _C, _D)],
    "one CP misread once": [screen(.3, _A, _B), screen(.3, [("96 HA", 398), ("Pikachu", 379), ("Pikachu", 334)], _B, _C), screen(.3, _A, _B, _C)],
    "a name cut short once": [screen(.3, _A, [("Pik", 379), ("Pichu", 255), ("Lego", 512)]), screen(.3, _A, _B)],
    "a screen that didn't move": [screen(.3, _A, _B), screen(.35, _A, _B)],
    "nothing but twins (lines up short: not used)": [screen(.3, _TWIN, _TWIN), screen(.3, _TWIN, _TWIN), screen(.3, _TWIN, _TWIN)],
}


def answer(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        return f"raises {type(e).__name__}"


DISTANCES = ["4.125.4 km", "4,125.4 km", "2,981.5 km", "2,981,5 km", "125.4 km", "87.3 km", "38533 km", "1,234 km", "no number"]


def answers():
    out = {}
    for name, fn in PAIRED.items():
        out[name] = {f"{g}\t{q}": answer(fn, g, q) for g, q in PAIRS}
    for name, fn in SINGLE.items():
        out[name] = {s: answer(fn, s) for s in ONE}
    for name, fn in NAMED.items():
        out[name] = {f"{g}\t{w}": answer(fn, g, w) for g, w in NAMES}
    for name, fn in COUNTERS.items():
        out[name] = {k: answer(fn, ts) for k, ts in COUNTS.items()}
    for name, fn in DIALOGS.items():
        out[name] = {k: answer(fn, ts) for k, ts in RENAMES.items()}
    out["mega.sheet"] = {k: answer(lambda ts: (lambda r: r and {x: r[x] for x in ("done_today", "mega_now", "level",
                                                                                 "more", "cost")} | {"button": bool(r["button"])})(mega.sheet(ts)), ts)
                         for k, ts in SHEETS.items()}
    out["ui.tiles"] = {k: answer(lambda ts: [t[:2] for t in ui.tiles(ts)], ts) for k, ts in LISTS.items()}
    out["search.grid_tiles"] = {k: answer(places, v) for k, v in GRIDS.items()}
    out["ui.classify"] = {k: answer(ui.classify, ts) for k, ts in SCREENS.items()}
    out["base.screen_changed"] = {k: answer(base.screen_changed, *v) for k, v in CHANGES.items()}
    out["mega.ask_cost"] ={k: answer(mega.ask_cost, ts) for k, ts in ASKS.items()}
    out["ui.gift_banner"] = {k: answer(ui.gift_banner, ts) for k, ts in BANNERS.items()}
    out["ui.profile_tabs"] = {k: answer(ui.profile_tabs, ts) for k, ts in BANNERS.items()}
    out["mega.form_of"] = {n: answer(mega.form_of, n) for n in NICKS}
    out["trade.km"] = {s: answer(lambda s: trade.km(SimpleNamespace(texts=[box(.4, .56, s)])), s) for s in DISTANCES}
    out["mega.badge"] = {k: answer(lambda ts: (lambda b: b and b[4])(mega.badge(ts)), ts) for k, ts in BADGES.items()}
    for whole_state in (False, True):
        gift.whole_state = whole_state
        out[f"gift.ours, whole_state {whole_state}"] = {f"{t} | {c}": answer(gift.ours, t, c) for t, c in GIFTS}
    gift.whole_state = False
    return json.loads(json.dumps(out))  # (tuples -> lists, as the file has them)


def main(a):
    now = answers()
    if a == ["--record"]:
        with open(GOLD, "w") as f:
            json.dump(now, f, indent=1, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        print(f"recorded {sum(map(len, now.values()))} answers from {len(now)} readers -> {GOLD}")
        return 0
    if a:
        sys.exit(__doc__)
    gold = json.load(open(GOLD))
    bad = 0
    for reader in sorted(set(gold) | set(now)):
        if reader not in now or reader not in gold:
            print(f"{reader}: {'gone' if reader not in now else 'new'} (run --record if that's meant)")
            bad += 1
            continue
        for case in sorted(set(gold[reader]) | set(now[reader])):
            g, n = gold[reader].get(case, "(no case)"), now[reader].get(case, "(no case)")
            if g != n:
                print(f"{reader}  {case!r}: was {g!r}, now {n!r}")
                bad += 1
    total = sum(map(len, gold.values()))
    print(f"{bad} changed of {total} answers" if bad else f"all {total} answers the same")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
