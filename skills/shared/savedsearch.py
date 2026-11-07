#!/usr/bin/env python3
"""The search list's saved searches: read their labels, run one, add to it, type a long search, and tag everything a
search finds (tag_pile: long press, SELECT ALL, tag)."""
import os, re, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import ui
import base
from base import Stop, log, keep_capture, go, look, wait_for
import search
from taps import press, select_all, settled_tiles
from tagsheet import still_sheet, search_exact
from rules import CLEAN

UNTAGGED_ONLY = {"PvpC1", "PvpC2", CLEAN}  # their own search already has !# (and on the Pixel PvpC1 fills the bar)


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
    guessed from where its letters sit in the box, and its count is unknown. The name must start a word in the box:
    100+km is no match for a 0-100km label"""
    k = key(name)
    if k in labs:
        t, n = labs[k]
        return t[0] + t[2] / 2, t[1], n
    for t, _ in labs.values():
        raw = t[4]
        keyed = [(i, key(c)) for i, c in enumerate(raw) if key(c)]  # the raw index of each key letter
        letters = "".join(c for _, c in keyed)
        at = letters.find(k)
        while at >= 0:
            first, last = keyed[at][0], keyed[at + len(k) - 1][0]
            if first == 0 or raw[first - 1].isspace():
                return t[0] + t[2] * (first + last + 1) / 2 / len(raw), t[1], None
            at = letters.find(k, at + 1)
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
            base.tap_x(bounds)  # the box's X
            time.sleep(1.0)
            continue
        got = results(texts)
        if got == 0 and n is None:  # no count on its label. A tap types nothing, so this is a real 0. A nudge here could
            log(f"{name}: 0")  # change it: a bar the search fills loses its last character (PvpC1 0 -> 1182, 2026-11-06)
            return 0
        if got == 0:  # its label says there are some: the game didn't run it
            if search.rerun_blank(None, bounds) is None:
                continue
            got = results()
            if got != n:  # the nudge changed the search, or the label is old: nothing may act on this list
                raise Stop(f"{name}: its label says {n}, but after a nudge the search shows {got}")
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
                return search.unblank(suffix, bounds)
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
    def give_up(why):
        texts, _, bounds = still_sheet()
        close_sheet(texts, bounds)
        raise Stop(why)
    # (ui.norm drops digits: 2XL is XL on the sheet)
    for t, v in [*((t, False) for t in off), *([(tag, True)] if tag else [])]:
        T = ui.norm(t)
        ticks = base.show_tag(T)
        if ticks is None:
            give_up(f"no {t} tag on this account: nothing tagged")
        if ticks.get(T) is v:  # the search said none have tag and all have off: a tick here is a misread or a partial mark
            give_up(f"{t} already shows {'a' if v else 'no'} tick for this lot: nothing tagged")
        if base.set_tick(T, v, t, ticks).get(T) is not v:
            keep_capture("tick")
            give_up(f"tapped {t} but its tick didn't change: nothing tagged")
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
