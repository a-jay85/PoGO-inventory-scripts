#!/usr/bin/env python3
"""Cleanup after trading: tag the saved searches, power up the Clean Trades ones that cross an XL tier, tag them Transfer.

  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py [--limit N]
  caffeinate -dimsu python3 cleantrades.py [--limit N]    the iPhone, through iPhone Mirroring
  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py --look    only step 2, and it only reads: CANCEL every time
  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py evo       steps 1 and 3
  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py fix       #Transfer&traded + a trade evolution: Transfer -> Evo
  POGO_PHONE=android caffeinate -dimsu python3 cleantrades.py transfer [--limit N]   step 2 for all of #Transfer
                                          (catches up the ones tagged before every tagger powered them up first)

Start with Pokémon GO on the Pokémon screen. Four steps, always in this order:
 1. Shortcuts PvpC1 and PvpC2 -> tag PvpC. Shortcut IV Check -> tag IVC. A shortcut this account doesn't have is
    skipped. This goes first: Clean Trades only shows untagged ones (!#), so these drop out of it.
 2. Clean Trades + &countcandyxl0-359 (under 360 Candy XL). Each one is opened and POWER UP tapped: the dialog's
    "CP a -> b" and Stardust cost narrow its level. Each + (one more power-up) shows new totals that narrow it
    more. At level 14, 19, 22 or 30 (or the half level after) it gets 1-2 power-ups in one go, to reach 15, 20, 23
    or 31: the next XL-on-transfer tier
    (~/claude-plans/_reports/personal/pogo/xl-transfer-roi.md). Anything else: CANCEL. Never below 1,000,000 Stardust.
 3. CyrillJan only (HashTagAJay doesn't need the XP): Clean Trades + a trade evolution (free once traded: Kadabra, Machoke, Graveler, Haunter, Boldore, Gurdurr,
    Karrablast, Shelmet, Phantump, Pumpkaboo) -> tag Evo. Not the base forms (Abra...).
 4. Clean Trades -> tag Transfer.
Before step 2, the never-traded ones that must not get Transfer leave the pile: Clean Trades &!traded&xxl (then xxs)
-> renamed XXL / xxs, tagged IVC (sizes.py); Clean Trades &!traded&!shadow + a trade evolution -> tag GIV.
Tagging: the shortcut's search + &!#<tag> (PvpC1, PvpC2 and Clean Trades as they are: they already exclude tagged ones), long press, SELECT ALL, TAG (n). n must equal the search's count, and
afterwards the same search must come back empty.
--limit N powers up at most N Pokémon (the tagging still runs). Log in runs/<time>/.
Every script that tags Transfer runs step 2 on that pile first (power_pile): tradeable.py too.
"""
import math, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, Skip, log, keep_capture, go, look, wait_for
import search, session
import pvp
from shadows import Pass, press, next_one, select_all, settled_tiles, exact, owned
from trades import sheet_rows, still_sheet, search_exact, tick, sheet_down


class Unsure(Pass):
    """left because something couldn't be read: it may still want a power-up, so it isn't done with"""

TAGGING = [("PvpC1", "PvpC"), ("PvpC2", "PvpC"), ("IV Check", "IVC")]
CLEAN, TRANSFER, EVO = "Clean Trades", "Transfer", "Evo"
UNTAGGED_ONLY = {"PvpC1", "PvpC2", CLEAN}  # their own search already has !# (and on the Pixel PvpC1 fills the bar)
# evolve free once traded: Kadabra, Machoke, Graveler (Alolan too), Haunter, Boldore, Gurdurr, Karrablast, Shelmet,
# Phantump, Pumpkaboo. Not the base forms (Abra...). Dex numbers:
# the names make a search too long for the bar to read back
TRADE_EVOS = "64,67,75,93,525,533,588,616,708,710"
EVO_FOR = "CyrillJan"  # the account that wants the XP: HashTagAJay transfers them like the rest
BIG = 10_000  # storage max: HashTagAJay 13,000, CyrillJan 7,875 (2026-10-22)
UNDER_360_XL = "&countcandyxl0-359"  # a count term eats what follows it: always last
DUST_FLOOR = 1_000_000
LOOK = False  # --look: read the levels, power up and tag nothing
PLAYS = {14: 15, 19: 20, 22: 23, 30: 31}  # level -> the tier it crosses into (2 taps, or 1 from the half level)
CANDY = {14: 2, 19: 2, 22: 3, 30: 4}  # candy per tap there (purified rounds up to the same)
DUST = [(1, 200), (3, 400), (5, 600), (7, 800), (9, 1000), (11, 1300), (13, 1600), (15, 1900), (17, 2200),
        (19, 2500), (21, 3000), (23, 3500), (25, 4000), (27, 4500), (29, 5000), (31, 6000), (33, 7000),
        (35, 8000), (37, 9000), (39, 10000)]  # (from level, Stardust a power-up)
DUST_RATE = (1, 0.5, 0.9, 0.45)  # normal, lucky, purified, both
PURIFIED_AT = 25  # purifying sets the level to 25
MAX_PLUS = 4  # + taps to find the level: from 19 the cost only jumps on the 5th power-up (at 21)


def key(s):
    """'Clean Trades' / 'CleanTrades' / 'Clean' + 'Trades' -> 'cleantrades'. 'PvpC1' read as 'PvpCl' still matches"""
    return re.sub(r"[il1|]", "l", re.sub(r"[^a-z0-9|]", "", s.lower()))


def same_l(s):
    """OCR mixes up l, i, I, 1 and | ('countcandyx10-359'), and reads '!' as ':', and sees a dot for it or next to it ('&.!ultrabeast')"""
    return re.sub(r"[il1|!:]", "l", re.sub(r"&\.!?", "&!", re.sub(r"\s", "", s.lower())))


# ---------- the saved searches ----------

def panel():
    """the search panel with an empty bar and the shortcuts showing -> texts, bounds. Android: the shortcuts show
    above the keyboard too, so it stays up (the texts on and just above it are left out)"""
    for attempt in range(3):
        if search.clear_search() == "list":
            search.open_panel(look()[3])
        for _ in range(8):
            time.sleep(search.POLL)
            path, bounds = ui.capture()
            texts = ui.ocr(path)
            fav = any(ui.norm(t[4]) == "FAVORITE" for t in texts)
            kb = next((t[1] for t in texts if ui.ANDROID and t[4].strip() == "?123" and t[1] > 0.5), None)
            if kb is not None:
                if fav:
                    return [t for t in texts if t[1] < kb - 0.3], bounds  # (its suggestion strip too)
                base.key("back")  # hides the keyboard only: the panel stays
                continue
            if fav:
                return texts, bounds
    keep_capture("panel")
    raise Stop("the search panel with the saved shortcuts didn't show")


def labels(texts):
    """shortcut labels on the panel -> {key: (top line's box, count under it or None)}. A label can wrap ('Clean' /
    'Trades'), and the count sits under the last line"""
    fav = next(t[1] for t in texts if ui.norm(t[4]) == "FAVORITE")
    rec = min([t[1] for t in texts if ui.norm(t[4]) == "RECOMMENDED"] or [1.0])
    boxes = sorted((t for t in texts if fav + 0.03 < t[1] < rec), key=lambda t: t[1])
    mid = lambda t: t[0] + t[2] / 2
    under = lambda t, u: 0.005 < u[1] - t[1] < 0.04 and abs(mid(t) - mid(u)) < 0.05
    out, used = {}, set()
    for t in boxes:
        if id(t) in used or re.fullmatch(r"[\d,]+", t[4].strip()):
            continue
        lines = [t]
        while (nxt := next((u for u in boxes if under(lines[-1], u) and id(u) not in used
                            and not re.fullmatch(r"[\d,]+", u[4].strip())), None)):
            lines.append(nxt)
            used.add(id(nxt))
        n = next((u for u in boxes if under(lines[-1], u) and re.fullmatch(r"[\d,]+", u[4].strip())), None)
        out[key("".join(l[4] for l in lines))] = (t, int(n[4].replace(",", "")) if n else None)
    return out


def find_label(labs, name):
    """name's label in labels() -> (its middle x, its top y, count or None), or None. Android OCR can read a
    whole row of labels as one box ('1 years old IV Check Need Candy Lucky Dex'): then the name's middle x is
    guessed from where its letters sit in the box, and its count is unknown"""
    k = key(name)
    if k in labs:
        t, n = labs[k]
        return t[0] + t[2] / 2, t[1], n
    for t, _ in labs.values():
        raw = t[4]
        keyed = [(i, key(c)) for i, c in enumerate(raw) if key(c)]  # the raw index of each key letter
        at = "".join(c for _, c in keyed).find(k)
        if at >= 0:
            first, last = keyed[at][0], keyed[at + len(k) - 1][0]
            return t[0] + t[2] * (first + last + 1) / 2 / len(raw), t[1], None
    return None


def results(texts=None):
    """the search ran: panel closed, list showing. -> its count (0 when no tiles). texts: a look taken after
    the search, read first"""
    for _ in range(16):
        if texts is None:
            time.sleep(search.POLL)
            _, texts, _, _ = look()
        if not ui.search_panel(texts) and ui.classify(texts) == "list":
            n = search.result_count(texts)
            if n is not None:
                return n
            if not ui.tiles(texts) and n is None:
                if not settled_tiles():
                    return 0
        texts = None
    keep_capture("results")
    raise Stop("the search didn't come back with a count")


def run_shortcut(name, suffix=""):
    """tap a saved search, then add suffix to its end. -> the count, or None if this account has no such shortcut"""
    for attempt in range(3):
        texts, bounds = panel()
        lab = find_label(labels(texts), name)
        if not lab:
            log(f"no {name!r} shortcut on this account: {sorted(labels(texts))}")
            search.close_panel(bounds)
            return None
        x, y, n = lab
        if n == 0:  # (a suffix only narrows it)
            log(f"{name}: 0")
            search.close_panel(bounds)
            return 0
        search.click(x, y - 0.055, bounds)  # the round button above the label
        _, texts, _, bounds = look()
        if any("MANAGE FAVORITE" in ui.norm(u[4]) for u in texts):  # the tap landed as a long press
            log(f"{name}: the shortcut tap was a long press: again")
            search.click(0.5, 0.937, bounds)  # the box's X
            time.sleep(1.0)
            continue
        got = results(texts)
        if not suffix:
            log(f"{name}: {got}")
            return got
        if append(suffix, bounds):
            got2 = results()
            log(f"{name} {suffix}: {got2} (of {got})")
            if got2 > got:
                raise Stop(f"{name}{suffix} shows {got2}, more than {name}'s {got}: the suffix didn't land as an AND")
            return got2
    keep_capture("shortcut")
    raise Stop(f"couldn't run the {name!r} shortcut{' + ' + suffix if suffix else ''}")


def append(suffix, bounds=None, before=None):
    """tap the filled bar, type suffix at the end, Return. False if the bar doesn't end with it (cleared after).
    before: the search already in the bar. When the bar still ends with it, nothing landed (the iPhone has lost a
    whole typed piece now and then): it types the piece once more"""
    search.LAST["q"] = None  # (the bar won't hold start_search's last one)
    bounds = bounds or look()[3]
    for tap in range(2):  # the iPhone drops a bar tap now and then: the list stays up, no panel
        search.click(0.45, 0.183, bounds, gap=search.BAR_GAP)
        for _ in range(10):
            time.sleep(search.POLL)
            if ui.search_panel(ui.ocr(ui.capture()[0])):
                break
        else:
            if tap:
                return False
            log("  the tap on the search bar didn't open it: tapping it again")
            continue
        break
    if ui.ANDROID:
        ui.android.shell("input keyevent KEYCODE_MOVE_END")
    else:
        base.key("right", cmd=True)
    want = same_l(suffix)
    if len(want) > 24:  # a long one doesn't fit in the bar: only its end shows
        want = want[-24:]
    old = same_l(before)[-16:] if before else None
    for attempt in range(2):
        base.type_text(suffix)
        for i in range(6):
            time.sleep(search.POLL)
            texts = ui.ocr(ui.android.sharp()) if ui.ANDROID and i % 2 else ui.ocr(ui.capture()[0])
            if any(same_l(t[4]).endswith(want) for t in texts):
                base.key("return")
                return True
        if attempt or not old or not any(same_l(t[4]).endswith(old) for t in texts):
            break
        log(f"  {suffix!r} didn't land in the bar: typing it again")
        if not ui.ANDROID:  # the panel can be up with no keyboard (a late 2nd bar tap): a tap in the bar brings it back
            search.click(0.45, 0.183, bounds, gap=search.BAR_GAP)
            time.sleep(0.8)
            base.key("right", cmd=True)
    keep_capture("append")
    log(f"the bar doesn't end with {suffix!r}: {[t[4] for t in texts if t[1] < 0.62 and '&' in t[4]]}")
    search.close_panel(bounds)
    return False


HEAD_MAX, PIECE_MAX = 28, 24  # what the Pixel's bar shows of a whole search, and what append() checks of its end


def long_search(q):
    """search_exact for a search too long to read back from the bar (it shows ~30 characters): type a head short
    enough to read back whole, then append the rest a few '&' terms at a time, each one's end checked, and none may
    grow the count. -> the count"""
    if len(q) <= 2 * HEAD_MAX:
        search_exact(q)
        return results()
    terms = re.split(r"(?=&)", q)
    head = terms.pop(0)  # (an AND's order doesn't matter: the terms that narrow it go first, the `&!` ones last,
    terms = sorted(dict.fromkeys(terms), key=lambda t: (t.startswith("&count"), t.startswith("&!")))  # so an empty
    # one stops early. No repeats. A count term eats what follows it: it goes after everything)
    while terms and len(head + terms[0]) <= HEAD_MAX:
        head += terms.pop(0)
    search_exact(head)
    n = results()
    done = head
    while terms and n:  # (0 stays 0: an AND only narrows it)
        piece = terms.pop(0)
        while terms and len(piece + terms[0]) <= PIECE_MAX:
            piece += terms.pop(0)
        if not append(piece, before=done):
            raise Stop(f"couldn't add {piece!r} to the search {q!r}")
        done += piece
        n2 = results()
        if n2 > n:
            raise Stop(f"adding {piece!r} showed {n2}, more than {n}: it didn't land as an AND")
        n = n2
    log(f"{q}: {n}")
    return n


def account():
    """which account, by the storage max over the empty search ('7874 / 7875'): HashTagAJay's is thousands higher"""
    for _ in range(3):
        search.clear_search()
        for _ in range(8):
            time.sleep(0.3)
            texts = look()[1]
            got = [int(m.group(1).replace(",", "")) for t in texts if t[1] < 0.15
                   and (m := re.fullmatch(r"\d[\d,]{2,}\s*/\s*(\d[\d,]{2,})\W?", t[4].strip()))]  # (not the 10/12 shortcuts)
            # \W?: on the iPhone the bar's edge can read as a '|' stuck on the end ('12900/12900|')
            if len(got) == 1:
                who = "HashTagAJay" if got[0] > BIG else EVO_FOR
                log(f"storage {got[0]:,}: {who}")
                return who
    keep_capture("account")
    raise Stop("can't read the storage max, so can't tell which account this is")


# ---------- tagging a whole search ----------

def tag_pile(name, tag, suffix=None, off=(), query=None):
    """tag everything in a shortcut's search + suffix (default: the ones that don't have the tag yet), and take the
    off tags away from them. query: a typed search instead of the shortcut. tag None: only take the off tags away. The
    search must leave out the tag itself (or have the off tags): afterwards the same search has to come back empty"""
    if suffix is None:
        suffix = "" if name in UNTAGGED_ONLY else f"&!#{tag}"
    find = (lambda: long_search(query)) if query else (lambda: run_shortcut(name, suffix))
    n = find()
    if not n:
        return 0
    btn, got, texts, bounds = select_all("TAG", n, poll=search.POLL)
    if got != n:
        keep_capture("count")
        search.leave_multiselect(texts, bounds)
        raise Stop(f"{name}: SELECT ALL picked {got}, but the search shows {n}: nothing tagged")
    press(btn, bounds)
    wait_for("tags")
    texts, path, bounds = still_sheet()
    head = " ".join(t[4] for t in texts if t[1] < 0.15)
    if not re.search(rf"TAG\s*{n}\s*POK", head.upper()):  # (ui.norm drops digits)
        close_sheet(texts, bounds)
        raise Stop(f"the tag sheet says {head!r}, wanted {n}")
    # tag -> its last tick, keyed like sheet_rows' names (ui.norm drops digits: 2XL is XL there)
    left, same = {**{ui.norm(t): False for t in off}, **({ui.norm(tag): True} if tag else {})}, 0
    for _ in range(30):
        rows = sheet_rows(texts, path)
        T = next((T for T in left if T in rows), None)
        if T:  # one at a time, then read the sheet again: a tick can move the rows
            box, ticked = rows[T]
            if ticked is left[T]:  # the search said none have tag and all have off: a tick here is a misread or a partial mark
                close_sheet(texts, bounds)
                raise Stop(f"{T} already shows {'a' if ticked else 'no'} tick for this lot: nothing tagged")
            tick(T, box, left[T], bounds, poll=search.POLL, on_fail=close_sheet)
            del left[T]
            texts, path, bounds = still_sheet()
            same = 0
            continue
        if not left:
            break
        before = [t[4] for t in texts]
        sheet_down(bounds)
        texts, path, bounds = still_sheet()
        same = same + 1 if [t[4] for t in texts] == before else 0
        if same >= 2:
            close_sheet(texts, bounds)
            raise Stop(f"no {', '.join(left)} tag on this account: nothing tagged")
    else:
        close_sheet(texts, bounds)
        raise Stop(f"couldn't find {', '.join(left)} in the tag sheet")
    texts, _, bounds = still_sheet()
    press(next(t for t in texts if ui.norm(t[4]) == "DONE"), bounds)
    wait_for("list", timeout=8)
    rest = results() and find()  # the list may drop them on its own: then no need to type the search again
    if rest:
        raise Stop(f"{name}: tagged {n} {tag or ''}, but {rest} are still in the search")
    log(f"{name}: tagged {n} {tag or ''}" + "".join(f", took off {t}" for t in off))
    return n


def close_sheet(texts, bounds):
    """leave the tag sheet unsaved (Android: the X under DONE), then multi-select"""
    if not ui.ANDROID:
        go("CANCEL", "list")
    else:
        d = next(t for t in texts if ui.norm(t[4]) == "DONE")
        press((d[0] + d[2] / 2 - 0.03, d[1] + 0.075, 0.06, 0.03, ""), bounds)
    _, texts, _, bounds = wait_for("list")
    search.leave_multiselect(texts, bounds)


# ---------- powering up ----------

def candidates(species, hp, a, b):
    """every (species, IVs, level) with this max HP, CP a, and CP b one power-up later"""
    out = []
    for sid in species:
        st = pvp.SPECIES[sid]["baseStats"]
        for lv in pvp.LEVELS[:-1]:
            m, m2 = pvp.cpm(lv), pvp.cpm(lv + 0.5)
            for h in range(16):
                if max(10, math.floor((st["hp"] + h) * m)) != hp:
                    continue
                for at in range(16):
                    for d in range(16):
                        iv = (at, d, h)
                        if pvp.cp(st, iv, lv) == a and pvp.cp(st, iv, lv + 0.5) == b:
                            out.append((sid, iv, lv))
    return out


def nickname_species(info, texts):
    """a nickname ('96 HA') names no species: the candy line and types (no taps), else the appraisal's 'This Gible
    was caught' line. Back on the detail page after. -> species, or [] if neither tells"""
    try:
        return base.species_from_candy(texts, info["cp"], info["hp"])
    except Skip as e:
        log(f"  {e}: asking the appraisal")
    base.open_appraisal()
    try:
        sp = base.appraisal_species(info["texts"])
        base.appraise()  # (the bars filled in: one tap closes it)
    except Skip as e:
        log(f"  {e}")
        sp = []
    go("dialog", "detail")
    return sp


def cp_levels(species, hp, cp):
    """every level some IVs give this CP and max HP at: no tap needed"""
    out = set()
    for sid in species:
        st = pvp.SPECIES[sid]["baseStats"]
        for lv in pvp.LEVELS:
            m = pvp.cpm(lv)
            hs = [h for h in range(16) if max(10, math.floor((st["hp"] + h) * m)) == hp]
            if any(pvp.cp(st, (at, d, h), lv) == cp for h in hs for at in range(16) for d in range(16)):
                out.add(lv)
    return sorted(out)


def dust_at(lv):
    """Stardust for one power-up from this level (before the lucky / purified discount)"""
    return next(c for first, c in reversed(DUST) if lv >= first)


def page_cost(texts):
    """the Stardust next to POWER UP on the detail page, or None if it can't be read"""
    btn = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[0] < 0.4 and t[1] > 0.6]
    if len(btn) != 1:
        return None
    got = [int(re.sub(r"\D", "", m.group(1))) for t in texts if abs(t[1] - btn[0][1]) < 0.02 and 0.4 < t[0] < 0.7
           and (m := re.fullmatch(r"(?:\S\s+|\D{0,3}?)(\d{1,2}[,.]\d{3}|\d{2,3})", t[4].strip()))]  # icon: '1 7,000'
    if len(got) != 1:
        return None
    if got[0] > 10_000 and got[0] % 1000:  # the icon read as a 1 with no space ('12,200'): XL costs are whole thousands
        return got[0] - 10_000
    return got[0]


def page_candy(texts):
    """the Candy next to the Stardust on the detail page's POWER UP row, or None if it can't be read (it often can't)"""
    btn = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[0] < 0.4 and t[1] > 0.6]
    got = [int(t[4].strip()) for t in texts if btn and abs(t[1] - btn[0][1]) < 0.02 and t[0] > 0.68
           and re.fullmatch(r"\d{1,2}", t[4].strip())]
    return got[0] if len(got) == 1 else None


def candy_at(lv):
    """Candy for one power-up from this level, under 40 (a purified one's rounds up to the same)"""
    return next(c for first, c in ((39, 15), (37, 12), (35, 10), (33, 8), (31, 6), (26, 4), (21, 3), (11, 2), (1, 1))
                if lv >= first)


def cost_levels(texts, cp):
    """-> (cost, every level the detail page's power-up cost fits). Lucky shows on the page. A purified one is always
    level 25 (3,600, or 1,800 lucky): purifying puts it there and it's transferred from there. No levels = a cost no
    table has, or no two looks in a row agreed on it"""
    cost = page_cost(texts)
    for _ in range(6):  # right after a swipe the page still slides: a cost read then can be another's (2,200 read as
        _, texts, _, _ = look()  # level 40+, 2026-10-23). Two looks in a row on this CP must agree
        again = page_cost(texts)
        if again == cost and ui.detail_info(texts)["cp"] == cp:
            break
        cost = again
    else:
        cost = None
    if cost is None:
        return None, []
    lucky = any(ui.norm(t[4]).startswith("LUCKY POK") for t in texts)
    rate, purified = DUST_RATE[1::2] if lucky else DUST_RATE[0::2]
    if cost == round(dust_at(PURIFIED_AT) * purified):
        return cost, [PURIFIED_AT]
    if cost > round(DUST[-1][1] * rate):  # past the table: an XL Candy power-up, level 40+
        return cost, [lv / 2 for lv in range(80, 100)]
    lvs = set()
    for i, (first, c) in enumerate(DUST):
        last = DUST[i + 1][0] if i + 1 < len(DUST) else 50
        if round(c * rate) == cost:
            lvs.update(first + k / 2 for k in range(int((last - first) * 2)))
    candy = page_candy(texts)  # splits a cost that spans a candy step: 4,000 is 3 Candy at 25-25.5, 4 at 26-26.5
    if candy is None and ui.ANDROID and len({candy_at(lv) for lv in lvs if lv < 40}) > 1:
        candy = page_candy(ui.ocr(ui.android.sharp()))  # the small digit mostly reads only at full size
    if candy and {lv for lv in lvs if candy_at(lv) == candy}:
        lvs = {lv for lv in lvs if candy_at(lv) == candy}
    return cost, sorted(lvs)


def read_dialog(cp, after=None):
    """the open power-up dialog. Wait until its first CP is the page's and (after a +) its 'after' CP has moved.
    -> (CP after, total dust, POWER UP box, CANCEL box, + box, bounds, title)"""
    for _ in range(25):
        time.sleep(search.POLL)
        _, texts, _, bounds = look()
        head = next((t for t in texts if re.match(r"POWER UP\s*:", t[4].strip(), re.I)), None)
        line = next((t for t in texts if re.fullmatch(r"CP\s*(\d+)\D+(\d+)", t[4].strip())), None)
        ok = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[1] > 0.75]
        no = exact(texts, "CANCEL")
        if not (head and line and len(ok) == 1 and len(no) == 1):
            continue
        a, b = map(int, re.fullmatch(r"CP\s*(\d+)\D+(\d+)", line[4].strip()).groups())
        if a != cp or b == after:  # (its CP must be the page's: 'CP 372 →385' can read as 'CP3 →72')
            continue
        dust = next((int(m.group(1).replace(",", "")) for t in texts if line[1] + 0.02 < t[1] < line[1] + 0.075
                     and (m := re.fullmatch(r"\D{0,3}?(\d{1,2},\d{3}|\d{3})", t[4].strip()))), None)
        plus = [t for t in texts if t[4].strip() == "+" and t[0] > 0.6 and line[1] < t[1] < ok[0][1]]
        if not plus and ui.ANDROID:  # the thin + on its pale ring mostly goes unread: it sits right of the cost.
            plus = [(0.723, line[1] + 0.058, 0.073, 0.04, "+?")]  # more() checks the CP moved
        return b, dust, ok[0], no[0], plus[0] if plus else None, bounds, head[4]
    keep_capture("powerdialog")
    raise Stop("no power-up dialog, or its CP didn't move after +")


def dialog(info):
    """tap POWER UP on the detail page. -> read_dialog() without the title"""
    _, texts, _, bounds = look()
    btn = [t for t in texts if ui.norm(t[4]) == "POWER UP" and t[1] > 0.6]
    if len(btn) != 1:
        raise Pass("can't find POWER UP")
    press(btn[0], bounds)
    *got, head = read_dialog(info["cp"])
    if ui.letters(head.split(":", 1)[1]) != ui.letters(info["name"]):
        press(got[3], got[5])
        raise Stop(f"the power-up dialog names someone else: {head!r} (wanted {info['name']})")
    return got


def more(cp, d):
    """tap + in the dialog: one more power-up. -> read_dialog() with the new totals"""
    if not d[4]:
        cancel(d[3], d[5])
        raise Unsure("no + in the power-up dialog")
    press(d[4], d[5])
    try:
        return read_dialog(cp, after=d[0])[:-1]
    except Stop:
        if d[4][4] != "+?":
            raise
        cancel(d[3], d[5])
        raise Unsure("tapped where + sits, but the dialog's CP didn't move")


def cancel(box, bounds):
    press(box, bounds)
    for _ in range(20):  # the detail shows through the dialog as it fades: wait for its title to go, or X can't be found
        texts = wait_for("detail")[1]
        if not any(re.match(r"POWER UP\s*:", t[4].strip(), re.I) for t in texts):
            return
        time.sleep(0.15)


def fits(c, rows):
    """does this (species, IVs, level) give every dialog row (n power-ups, CP after, total dust)?"""
    sid, iv, lv = c
    st = pvp.SPECIES[sid]["baseStats"]
    if any(pvp.cp(st, iv, lv + 0.5 * n) != b for n, b, _ in rows):
        return False
    return any(all(t is None or t == sum(round(m * dust_at(lv + 0.5 * k)) for k in range(n)) for n, _, t in rows)
               for m in DUST_RATE)


def steps(cands):
    """power-ups each possible level needs to reach its XL tier (None: not a play)"""
    return {int((PLAYS[math.floor(lv)] - lv) * 2) if math.floor(lv) in PLAYS else None for _, _, lv in cands}


def power_up(info, texts, levels=None):
    """1-2 power-ups if this one sits right under an XL tier. -> power-ups made. Raise Pass to leave it.
    Its level comes from the dialog: + adds a power-up, and each total (CP after, Stardust) rules levels out.
    levels: the caller's, used when the page's cost doesn't read"""
    cost, lvs = cost_levels(texts, info["cp"])
    lvs = lvs or sorted(levels or ())
    if not lvs:
        raise Unsure(f"can't read the power-up cost ({cost})")
    if not any(math.floor(lv) in PLAYS for lv in lvs):  # the cost rules out every play: no taps
        raise Pass(f"{cost} dust a power-up means level {lvs[0]}-{lvs[-1]}: none is {'/'.join(map(str, PLAYS))}")
    species = ui.species_for(info["name"], info["texts"]) or nickname_species(info, texts)
    if not species:
        raise Unsure(f"{cost} dust: don't know the species of {info['name']!r}")
    if info["cp"] is None:
        raise Unsure(f"{cost} dust: can't read its CP")
    have_dust, have_candy = owned(texts)
    if have_dust < DUST_FLOOR:
        raise Stop(f"Stardust {have_dust:,} is under {DUST_FLOOR:,}: no more power-ups")
    cp = info["cp"]
    d = dialog(info)
    rows = [(1, d[0], d[1])]
    cands = [c for c in candidates(species, info["hp"], cp, d[0]) if fits(c, rows)]
    while len(steps(cands)) > 1 and len(rows) < MAX_PLUS + 1:  # a play for some levels only: one more +
        d = more(cp, d)
        rows.append((len(rows) + 1, d[0], d[1]))
        cands = [c for c in cands if fits(c, rows)]
    lvs = sorted({lv for _, _, lv in cands})
    need = steps(cands)
    say = f"level {lvs or '?'} (CP{cp} -> " + ", ".join(f"{n}x: CP{b} {t} dust" for n, b, t in rows) + ")"
    if len(need) != 1 or None in need:
        cancel(d[3], d[5])
        raise Pass(f"{say}: no XL tier one or two power-ups away")
    n = need.pop()
    target = PLAYS[math.floor(lvs[0])]
    if n != len(rows):  # the dialog shows more power-ups than it needs: open it again and count up
        cancel(d[3], d[5])
        d = dialog(info)
        for _ in range(n - 1):
            d = more(cp, d)
    after, total = d[0], d[1]
    want = {pvp.cp(pvp.SPECIES[s]["baseStats"], iv, lv + 0.5 * n) for s, iv, lv in cands}
    if after not in want:  # (IVs that fit can still part ways on the CP n power-ups later: the level is the same)
        cancel(d[3], d[5])
        raise Stop(f"{n} power-up(s) should give CP{sorted(want)}, the dialog says CP{after}")
    candy = sum(CANDY[math.floor(lvs[0])] for _ in range(n))
    if have_candy < candy:
        cancel(d[3], d[5])
        raise Pass(f"{say}: needs {candy} candy, has {have_candy}")
    if total is None or have_dust - total < DUST_FLOOR:
        cancel(d[3], d[5])
        raise Stop(f"Stardust {have_dust:,} - {total} would drop under {DUST_FLOOR:,}: no more power-ups")
    log(f"  {say} -> {target}: {n} power-up(s), CP{after}, {total:,} dust")
    if LOOK:
        cancel(d[3], d[5])
        raise Pass(f"--look: would power up level {lvs} to {target}")
    press(d[2], d[5])
    end, tapped = time.time() + 30, time.time()
    while time.time() < end:  # done = dialog gone, the detail shows the new CP
        time.sleep(search.POLL)
        screen, t2, _, b2 = look()
        again = time.time() - tapped > 3  # a tap can miss: tap again while the same box is still up
        no = exact(t2, "NO")
        if len(no) == 1 and any("really want to power up" in t[4] for t in t2):
            if again:
                yes = exact(t2, "YES")  # (YES is white on green: OCR mostly misses it)
                press(yes[0] if len(yes) == 1 else (no[0][0], no[0][1] - 0.078, no[0][2], no[0][3], "YES"), b2)
                tapped = time.time()
            continue
        head = any(re.match(r"POWER UP\s*:", t[4].strip(), re.I) for t in t2)
        if head:  # still the power-up box: retap POWER UP only while it shows this same power-up
            same = any((m := re.fullmatch(r"CP\s*(\d+)\D+(\d+)", t[4].strip())) and m.groups() == (str(cp), str(after))
                       for t in t2)
            ok = [t for t in t2 if ui.norm(t[4]) == "POWER UP" and t[1] > 0.75]
            if again and same and len(ok) == 1:
                log(f"  the POWER UP tap didn't take: again")
                press(ok[0], b2)
                tapped = time.time()
            continue
        if screen == "detail" and ui.detail_info(t2)["cp"] == after:
            return n
    keep_capture("powerup")
    raise Stop(f"the power-up to CP{after} didn't show in 30s")


def power_walk(limit, query=None):
    """open each Clean Trades one (query: each one in this typed search) with under 360 XL and power up those right
    under a tier. -> how many got it, or None if --limit stopped it"""
    if not (long_search(query + UNDER_360_XL) if query else run_shortcut(CLEAN, UNDER_360_XL)):
        log(f"no {query or CLEAN} ones under 360 XL")
        return 0
    go("tile 1", "detail")
    seen, done, passed, t_start, again = set(), 0, 0, time.time(), False
    unseen = lambda t: (lambda n: (n["name"], n["cp"], n["hp"]))(ui.detail_info(t)) not in seen
    while True:
        t0 = time.time()
        for _ in range(10):  # right after a swipe the CP sparkles in and can read blank
            _, texts, _, _ = wait_for("detail")
            info = ui.detail_info(texts)
            if info["cp"] is not None:
                break
            time.sleep(0.2)
        me = (info["name"], info["cp"], info["hp"])
        if me in seen:  # a read mid-swipe can look like another one while the page hasn't moved: one more swipe
            if again or not next_one(None, unseen, poll=search.POLL):
                log("swiped back onto one already seen: end of the list")
                break
            again = True
            continue
        again = False
        seen.add(me)
        if done >= limit:
            log(f"--limit {limit} reached")
            return None  # (the rest weren't checked)
        try:
            try:
                taps = power_up(info, texts)
            except Unsure as e:  # mostly a read while the page still slid: one more go on a fresh look
                log(f"  {e}: looking again")
                time.sleep(0.5)
                texts = wait_for("detail")[1]
                info = {**info, **{k: v for k, v in ui.detail_info(texts).items() if v is not None}}
                taps = power_up(info, texts)
        except Pass as e:
            passed += 1
            log(f"pass {info['name']} CP{info['cp']}: {e}")
        else:
            done += 1
            info2 = ui.detail_info(wait_for("detail")[1])
            seen.add((info2["name"], info2["cp"], info2["hp"]))
            log(f"powered up {info['name']} CP{info['cp']} -> CP{info2['cp']}, {taps} power-up(s)  ({time.time() - t0:.1f}s)")
        if not next_one(None, unseen, poll=search.POLL):
            break
    log(f"powered up {done}, passed {passed}, {time.time() - t_start:.0f}s")
    go("close", "list")
    return done


def power_pile(query, limit):
    """power_walk for a pile about to be tagged Transfer. Running out of Stardust only ends the power-ups.
    -> False if --limit stopped it (the rest weren't checked: don't tag them yet)"""
    try:
        if power_walk(limit, query) is None:
            log(f"--limit {limit}: the rest of {query} weren't checked, so they aren't tagged Transfer")
            return False
    except Stop as e:
        if "Stardust" not in str(e):
            raise
        log(f"stopped powering up: {e}")
        if look()[0] != "list":
            go("close", "list")
    return True


def untraded():
    """the user's rules (2026-10-31): a never-traded one in Clean Trades never gets Transfer. XXL/xxs: renamed and
    tagged IVC (sizes.py). A trade evolution (not a shadow: it can't be traded): GIV. Both drop out of Clean Trades (!#)"""
    import sizes  # (sizes imports this file)
    for size in sizes.NAMES:
        sizes.walk(lambda: run_shortcut(CLEAN, f"&!traded&{size}"), size, 10 ** 9)
    tag_pile(CLEAN, "GIV", f"&!traded&!shadow&{TRADE_EVOS}")


def script(a):
    limit = session.limit(a)
    base.start()  # from anywhere, Pokémon GO closed too
    search.to_search_list()
    who = None if LOOK else account()
    if who != EVO_FOR and ("evo" in a or "fix" in a):
        raise Stop(f"signed in as {who!r}: only {EVO_FOR} tags free evolutions Evo")
    if LOOK:
        power_walk(limit)
        return
    if "evo" in a:  # steps 1 and 3: a PvpC/IVC one tagged Evo first would drop out of its shortcut (!#)
        for name, tag in TAGGING:
            tag_pile(name, tag)
        tag_pile(CLEAN, EVO, f"&{TRADE_EVOS}")
        return
    if "transfer" in a:  # every Transfer one: the cheap jump to an XL tier before it's transferred
        power_pile(f"#{TRANSFER}", limit)
        return
    if "fix" in a:  # Transfer tags given before the Evo step: traded trade evolutions go Transfer -> Evo
        tag_pile(TRANSFER, EVO, off=[TRANSFER], query=f"#{TRANSFER}&traded&{TRADE_EVOS}")
        return
    for name, tag in TAGGING:  # first: Clean Trades (!#) must only see what's left untagged after these
        tag_pile(name, tag)
    untraded()  # before the power-ups: these won't be transferred
    try:
        if power_walk(limit) is None:
            log(f"--limit {limit}: the rest weren't checked, so Clean Trades isn't tagged Transfer")
            return
    except Stop as e:
        if "Stardust" not in str(e):
            raise
        log(f"stopped powering up: {e}")
        if look()[0] != "list":
            go("close", "list")
    if who == EVO_FOR:
        tag_pile(CLEAN, EVO, f"&{TRADE_EVOS}")  # first: these drop out of Clean Trades (!#)
    tag_pile(CLEAN, TRANSFER)


if __name__ == "__main__":
    a = sys.argv[1:]
    if any(x not in ("--limit", "--look", "evo", "fix", "transfer") and not x.isdigit() for x in a):
        sys.exit(__doc__)
    LOOK = "--look" in a
    base.new_run_dir(os.path.join(HERE, "runs"))
    session.main(script, a)
