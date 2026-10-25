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
for d in ("pvpc", "cleanup", "dex", "trade", "gift", "ivc", "ivcsort"):  # (pvpc first: its run.py is `run`)
    sys.path.append(os.path.join(SKILLS, d))

import run, search, ui  # noqa: E402  (pvpc's run.py: first on the path)
import trades, cleantrades, dex, trade, gift  # noqa: E402


def by_path(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SKILLS, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ivc_run = by_path("ivcrun", "ivc/run.py")
ivcsort_run = by_path("ivcsort_run", "ivcsort/run.py")
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

# ---------- readers ----------


def strict(got, q):
    trades._views.clear()
    return [trades.strict(got, q), list(map(list, trades._views))]


def in_bar(phone):
    def f(got, q):
        p = SimpleNamespace(name=phone, texts=texts((0.1, got)))
        return trade.in_bar(p, q)
    return f


PAIRED = {
    "search.same_query": search.same_query,
    "search.bar_shows": search.bar_shows,
    "search.amp_as_8": search.amp_as_8,
    "dex.bar_holds": lambda g, q: dex.bar_holds(g.replace(" ", ""), q),
    "dex.bar_read": lambda g, q: dex.bar_read(texts((0.1, g))),
    "trades.strict": strict,
    "trade.in_bar ios": in_bar("ios"),
    "trade.in_bar android": in_bar("android"),
}
SINGLE = {
    "trade.same_l": trade.same_l,
    "trade.pile": trade.pile,
    "cleantrades.same_l": cleantrades.same_l,
    "cleantrades.key": cleantrades.key,
    "run.short": run.short,
    "ivcsort.short": ivcsort_run.short,
}
NAMED = {
    "run.same_name": run.same_name,
    "ivc.same_name": ivc_run.same_name,
    "ivcsort.same_name": ivcsort_run.same_name,
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


def answer(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        return f"raises {type(e).__name__}"


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
