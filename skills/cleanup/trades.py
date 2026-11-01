#!/usr/bin/env python3
"""Cleanup's shared reads and taps: a search typed until the bar reads back exactly, who's on the detail page (name, CP,
HP, weight, height), its tag chips, the caught date at the bottom of the page, and the tag sheet's rows and ticks.

It used to retag Nope legendaries, Ultra Beasts, Meltan and Melmetal (Remote Trade + RT, or Spot Transfer). Nothing
tags Nope now: ../shared/verdict.py gives those tags at the door, with the same rules.
"""
import datetime, os, random, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log, keep_capture, go, look, wait_for
import search
from shadows import press, exact

# ---------- search: start and end of the bar both read back ----------

_views = []


def strict(got, q):
    """the bar text vs q, symbol for symbol, off the phone's own screenshot on Android. A long search shows only its
    end while typing and only its start after Return: note which part matched, search_exact() adds them up.
    The sharp read can drop a thin last letter ('...,!xx' for '...,!xxl') that the caller's read has: either read
    showing all of it counts."""
    reads = [got]
    if ui.ANDROID:
        box = ui.search_box(ui.ocr(ui.android.sharp()))
        if box:  # (the search panel's bar isn't found that way: keep the caller's read)
            reads.insert(0, ui.search_text(box))
    views = [v for v in (bar_view(g, q) for g in reads) if v]
    if not views:
        return False
    _views.append(next((v for v in views if v[0] == "all"), views[0]))
    return True


def bar_view(got, q):
    """-> ('all' | 'end' | 'start', how many symbols) of q this read of the bar shows, or None"""
    s = re.sub(r"\s", "", got or "").lower()
    s = re.sub(r"^[<‹]?[q9]?(?=#)", "", s)  # the magnifier glued on
    s = re.sub(r"^[,.'`]+", "", s)  # the panel's cursor end can read as a stray ","
    Q = re.sub(r"\s", "", q).lower()
    if Q.startswith("#") and s.startswith("9") and s[1:2] != "#":  # a first '#' alone can read as '9' ('9nope&#old')
        s = "#" + s[1:]
    s, Q = re.sub(r"[i|]", "l", s), re.sub(r"[i|]", "l", Q)  # OCR reads 'xxl' as 'xxI' or 'xx|': one letter here
    bang = re.sub(r"^[q9]?[il|]", "!", s)  # the end of a long search: a '!' at its start reads as 'I' or 'QI'
    if bang != s and len(s) >= 15 and Q.endswith(bang):
        s = bang
    # the iPhone reads a '!' as 'l' anywhere ('!shadow&llucky'). Only where q has a '!': a lost one still fails (shorter)
    same = lambda a, b: len(a) == len(b) and all(x == y or (y == "!" and x == "l") for x, y in zip(a, b))
    if same(s, Q):
        return "all", len(s)
    if 15 <= len(s) < len(Q) and same(s, Q[-len(s):]):
        return "end", len(s)
    if 15 <= len(s) < len(Q) and same(s, Q[:len(s)]):
        return "start", len(s)
    return None


def ios_start(q):
    """iPhone: a long search shows only its end, after Return too. Open the bar, put the cursor at the start
    (cmd+Left) and read that, then Return again (the same search)"""
    bounds = look()[3]
    search.click(0.45, 0.183, bounds, gap=search.BAR_GAP)
    for _ in range(10):
        time.sleep(0.3)
        if ui.search_panel(ui.ocr(ui.capture()[0])):
            break
    else:
        return
    base.key("left", cmd=True)
    for _ in range(6):
        time.sleep(0.3)
        got, _ = search.panel_text()
        if strict(got, q) and _views[-1][0] in ("start", "all"):
            break
    base.key("return")
    for _ in range(16):
        time.sleep(0.25)
        texts = look()[1]
        if not ui.search_panel(texts) and ui.classify(texts) == "list":
            return


def search_exact(q):
    Q = re.sub(r"\s", "", q)
    for attempt in range(3):
        _views.clear()
        search.start_search(q, check=strict)
        got = {}
        for k, n in _views:
            got[k] = max(got.get(k, 0), n)
        if not ui.ANDROID and "all" not in got and "start" not in got and got.get("end"):
            ios_start(q)
            for k, n in _views:
                got[k] = max(got.get(k, 0), n)
        if "all" in got or got.get("start", 0) + got.get("end", 0) > len(Q):
            return
        log(f"only part of {q!r} read back ({got}): typing it again")
    keep_capture("search")
    raise Stop(f"couldn't read back all of {q!r} in the search bar")


# ---------- one Pokémon ----------

def who(texts):
    """name, CP, HP, weight, height: twins with the same name and CP still differ in weight and height"""
    info = ui.detail_info(texts)
    kg = next((t[4].strip() for t in texts if re.fullmatch(r"[\d.,]+\s*kg", t[4].strip())), None)
    m = next((t[4].strip() for t in texts if re.fullmatch(r"[\d.,]+\s*m", t[4].strip())), None)
    return info, ((info["name"] or "").replace(" ", ""), info["cp"], info["hp"], kg, m)  # OCR reads "80 h" or "80h"


def tag_chips(texts):
    """the tags under the name: between the HP line and the weight row (they can wrap onto two lines)"""
    hp = next(t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4]))
    kg = [t[1] for t in texts if re.fullmatch(r"[\d.,]+\s*kg", t[4].strip()) and t[1] > hp[1]]
    low = min(kg) if kg else hp[1] + 0.06
    return sorted(n for t in texts if hp[1] + 0.005 < t[1] < low - 0.005
                  and (n := re.sub(r"^[A-Z] (?=[A-Z]{2})", "", ui.norm(t[4])))  # Remote Trade's icon: "c Remote Trade"
                  and n not in ("DYNAMAX", "GIGANTAMAX") and not n.startswith("LUCKY POK"))


def scrolled_bottom(bounds, drags=2):
    """drag the detail page up to its bottom (caught date) -> texts seen there, both reads. drags: how many it takes
    from where the page is now"""
    for _ in range(drags):
        base.drag(0.08, 0.75, 0.08, 0.2, bounds)  # down the left edge: no buttons there
    reads = []
    for _ in range(2):
        _, texts, _, _ = look()
        reads.append(texts)
        if ui.ANDROID:
            reads.append(ui.ocr(ui.android.sharp()))
            break
        time.sleep(0.3)
    return reads


def back_to_top(me, bounds):
    """drag down until the CP shows. Only drag from labels that are never buttons (weight, candy, the caught box,
    form text), never from the top strip: a drag there pulls down the phone's notification shade.
    A drag at the top closes the page, so check a fresh read before each drag and size it from the weight row."""
    for _ in range(12):
        texts = look()[1]  # the phone's own screenshot
        now = who(texts)[1] if ui.classify(texts) == "detail" else None
        cp_top = any(t[1] < 0.15 and re.match(r"[cC]\s*[pP]", t[4].strip()) for t in texts)
        if now and (now[1:3] == me[1:3] and now[1] is not None  # same CP and HP (name reads can wobble). No CP read
                    # in either: not proof (half way down, 2026-10-31), the next line needs the CP at the top
                    or cp_top and None in (now[1], me[1]) and None not in me[2:] and now[2:] == me[2:]):
            return  # (a lucky one's sparkles can garble the CP, in this read or the first: then the same HP, weight
            # and height, with a CP at the top)
        if any(re.fullmatch(r"[cC]\s*[pP]\s*\d+", t[4].strip()) for t in texts):
            time.sleep(0.3)  # CP in sight: at the top, maybe still settling
            continue
        kg = [t for t in texts if re.search(r"\d\s*kg$", t[4].strip())]
        hold = [t for t in texts if 0.1 < t[1] < 0.8 and (t in kg or re.search(
            r"WEIGHT|HEIGHT|STARDUST|CANDY|CAUGHT|HATCHED|OBTAINED IN A TRADE|RECEIVED|MAX MOVES|WITH YOUR PARTY|THIS POK|BECOME|CAN USE|CAN FUSE|ADVENTURE EFFECT|DISTORTS", ui.norm(t[4])))]
        if hold:
            x, y = hold[0][0] + hold[0][2] / 2, hold[0][1] + hold[0][3] / 2
            # at the top the weight sits at ~0.6: move it to just short of there, any more and the page closes
            far = random.uniform(0.56, 0.58) - kg[0][1] if kg else random.uniform(0.4, 0.45)
            # (no CP in sight, so not at the top yet: a drag under 0.06 can leave it a hair short, the CP under the clock)
            base.drag(x, y, x, min(y + max(far, 0.06), 0.92), bounds)  # (drag waits for it to stop)
        else:
            time.sleep(0.3)
    keep_capture("top")
    raise Stop(f"couldn't get back to the top of the detail page (wanted {me}, read {now})")


def caught(texts):
    ds = {m for t in texts for m in re.findall(r"\b(\d{1,2}/\d{1,2}/20\d\d)\b", t[4])}
    if len(ds) != 1:
        return None
    try:
        return datetime.datetime.strptime(ds.pop(), "%m/%d/%Y").date()
    except ValueError:
        return None


# ---------- the tag sheet ----------

def sheet_rows(texts, path):
    """tag rows that are safe to tap (not under the fade at the bottom): norm name -> (box, ticked)"""
    def name(s):  # the icon by Remote Trade reads as a stray letter: "c Remote Trade"
        return re.sub(r"^[A-Z] (?=[A-Z]{2})", "", ui.norm(s.lstrip("•· ")))
    ticks = dict((name(n), on) for n, on in ui.ticked_tags(path, texts))
    rows = {}
    for t in texts:
        n = name(t[4])
        if n in ticks and 0.2 < t[1] < 0.7:
            rows[n] = (t, ticks[n])
    return rows


def still_sheet():
    last = None
    for _ in range(10):
        _, texts, path, bounds = wait_for("tags")
        ys = [(t[4], round(t[1], 2)) for t in texts]  # (boxes jitter a little between reads of a still screen)
        if ys == last:
            return texts, path, bounds
        last = ys
        time.sleep(0.25)
    return texts, path, bounds


def tick(T, box, want, bounds, poll=0.15, name=None, on_fail=None):
    """tap row T's box and wait until its tick reads want. on_fail(texts, bounds) backs out before the Stop"""
    press(box, bounds)
    for _ in range(20):
        time.sleep(poll)
        _, t2, p2, _ = wait_for("tags")
        r = sheet_rows(t2, p2)
        if T in r and r[T][1] is want:
            break
    else:
        keep_capture("tick")
        if on_fail:
            on_fail(t2, bounds)
        raise Stop(f"tapped {name or T} but its tick didn't change")
    if ui.ANDROID:
        ui.android.fresh()


def sheet_down(bounds):
    """scroll the tag sheet a small step: a big scroll skips rows"""
    base.drag(0.3, 0.62, 0.3, 0.4, bounds)
    if ui.ANDROID:
        ui.android.fresh()


def cancel_sheet():
    """leave the tag sheet unsaved. Android's sheet has no CANCEL, only the X under DONE"""
    _, texts, _, bounds = look()
    if not ui.ANDROID:
        go("CANCEL", "detail")
        return
    d = next(t for t in texts if ui.norm(t[4]) == "DONE")
    press((d[0] + d[2] / 2 - 0.03, d[1] + 0.075, 0.06, 0.03), bounds)
    wait_for("detail")


def done_sheet(texts, bounds):
    """tap DONE (where the last read of the sheet saw it) -> the detail page's texts. One caught in the last month
    gets a popup first ("Cannot Trade Recently Caught Pokémon Remotely ... will keep the Remote Trade tag"):
    its OK saves the tags"""
    press(next(t for t in texts if ui.norm(t[4]) == "DONE"), bounds)
    end, again = time.time() + 8, True
    while time.time() < end:
        time.sleep(0.15)
        screen, texts, _, bounds = look()
        if screen == "detail":
            return texts
        if any("RECENTLY CAUGHT" in ui.norm(t[4]) for t in texts) and exact(texts, "OK"):
            log("  recently caught: OK on the popup (it keeps the Remote Trade tag)")
            press(exact(texts, "OK")[0], bounds)
            end = time.time() + 6
        elif screen == "tags" and again and time.time() > end - 5:
            log("  tap DONE didn't land, again")
            press(next(t for t in texts if ui.norm(t[4]) == "DONE"), bounds)
            again = False
    keep_capture("done")
    raise Stop("after DONE: never got back to the detail page")
