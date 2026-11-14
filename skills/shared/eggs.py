#!/usr/bin/env python3
"""The Eggs tab: read the eggs, put the best one in the free ∞ incubator, and set the hatch timer. The Pixel only.

hatch.py (after its fresh start and hatches) and account.py (after every run's advsync, 2026-11-14) both use it:
fill_and_time() does the work on the Eggs tab, check() goes there from the map and back.

1. On the Eggs tab each egg reads "walked / km". A teal label is an egg in an incubator. The egg with the most km
   that isn't in one is opened, INCUBATE, and the ∞ incubator is taken only if it's free: the picker's first slot
   with no "N USE" under it. A paid incubator (1, 2 or 3 uses) is never tapped (the user, 2026-11-13).
2. The next hatch run: max(8, 7 x the km left) minutes from now, read off the incubated egg that has the least left.
   The km shown is what's left to walk, bonus and all (a 10 km egg showed "0 / 5 km" during a half-distance bonus:
   35 min, the user, 2026-11-13). 8 min at least: 1 km is the smallest egg (the daily 1 km one, or a 2 km one with
   a half-distance bonus; the user, 2026-11-14). Nothing incubating: the timer goes off.
"""
import re
from PIL import Image

import ui
import base
from base import Stop, log, keep_capture
import home, timer

EGG_ABOVE = 0.06  # an egg sits this far above its "walked / km" label
INFINITE = (0.145, 0.77)  # the incubator picker's first slot: the ∞ one when it's free
FREE_SLOT_X = 0.25  # a "N USE" label left of this is under the first slot: the ∞ is busy, that slot is a paid one
TEAL_MIN = 15  # teal pixels in a label that make it an incubating egg's (2026-11-13: 46 and 85 teal, the rest 0)
MIN_PER_KM, MIN_MINUTES = 7, 8  # the user's rule: 7 min a km, 8 at least (a 1 km egg)
RETRY_MINUTES = 15  # eggs, but none went in (the ∞ never showed free): look again this much later
USE_RE = re.compile(r"\d+\s*USES?", re.I)  # a paid incubator's '1 USE' under its slot
KM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*km", re.I)


# ---------- reading ----------

def oh(texts):
    return any(t[4].strip() == "Oh?" for t in texts)


def label(texts, word):
    return next((t for t in texts if ui.norm(t[4]) == word), None)


def eggs_tab(texts):
    """the Pokémon screens' EGGS tab, with its eggs: its tab label and at least one 'walked / km'"""
    return bool(label(texts, "EGGS")) and any(KM_RE.search(t[4]) for t in texts)


def teal(path, t):
    """how many teal pixels the label has: an incubating egg's number is teal, the others grey"""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    box = (int(t[0] * w), int(t[1] * h), int((t[0] + t[2]) * w), int((t[1] + t[3]) * h))
    px = im.crop(box).tobytes()
    return sum(1 for i in range(0, len(px), 3) if px[i + 1] - px[i] > 60 and px[i + 2] - px[i] > 60)


def eggs(path, texts):
    """-> [(walked, km, incubating, label box)], top to bottom"""
    out = []
    for t in sorted(texts, key=lambda t: (round(t[1], 2), t[0])):
        m = KM_RE.search(t[4])
        if m:
            out.append((float(m.group(1)), float(m.group(2)), teal(path, t) >= TEAL_MIN, t))
    return out


def look():
    return base.look(home.where)


def said(have):
    return ", ".join(f"{w:g}/{k:g}{' (incubating)' if i else ''}" for w, k, i, _ in have)


# ---------- the steps ----------

def to_eggs():
    """from the map to the Eggs tab: home.start() to the Pokémon list (a hatch on the way is tapped through), then
    the EGGS tab"""
    home.start()
    for _ in range(3):
        screen, texts, path, bounds = look()
        if eggs_tab(texts):
            return
        tab = label(texts, "EGGS")
        if not tab:
            break
        base.tap_box(tab, bounds, rest=1.5)
    keep_capture("eggs")
    raise Stop("couldn't open the Eggs tab")


def read_eggs():
    """the Eggs tab read until its eggs show -> (eggs, bounds)"""
    got = base.settle(lambda: look(), lambda g: eggs_tab(g[1]), timeout=5)
    screen, texts, path, bounds = got
    if not eggs_tab(texts):
        keep_capture("eggs")
        raise Stop(f"not on the Eggs tab: {ui.summary(texts, 100)}")
    return eggs(path, texts), bounds


def incubate(egg, bounds):
    """open this egg, INCUBATE, and the ∞ incubator if it's free. Back on the Eggs tab at the end.
    -> True if it went in"""
    walked, km, _, t = egg
    log(f"opening a {km:g} km egg")
    base.click(t[0] + t[2] / 2, t[1] - EGG_ABOVE, bounds, fuzz=0.01, rest=1.5)
    _, texts, _, bounds = base.settle(look, lambda g: label(g[1], "INCUBATE"), timeout=6)
    button = label(texts, "INCUBATE")
    if not button:
        log(f"  no INCUBATE on its page: {ui.summary(texts, 80)}")
        leave_to_eggs()
        return False
    base.tap_box(button, bounds, rest=1.0)
    uses = lambda ts: [x for x in ts if USE_RE.fullmatch(x[4].strip())]  # not 'Use an Incubator to hatch...'
    _, texts, _, bounds = base.settle(look, lambda g: label(g[1], "INCUBATORS") and uses(g[1]), timeout=6)
    if not label(texts, "INCUBATORS"):
        keep_capture("picker")
        log(f"  the incubator picker didn't open: {ui.summary(texts, 80)}")
        leave_to_eggs()
        return False
    first = min((x[0] for x in uses(texts)), default=1.0)
    if first < FREE_SLOT_X:
        log("  the ∞ incubator is busy (only paid ones in the picker): leaving it")
        keep_capture("busy")
        leave_to_eggs()
        return False
    log("  into the ∞ incubator")
    base.click(*INFINITE, bounds, fuzz=0.01, rest=1.5)
    leave_to_eggs()
    return True


def leave_to_eggs():
    """the X until the Eggs tab shows (the picker, then the egg's page). An incubated egg's page goes back by itself
    (in about 2 s): the X waits for that, or it would close the Eggs tab"""
    for i in range(3):
        screen, texts, path, bounds = base.settle(look, lambda g: eggs_tab(g[1]), timeout=3 if i == 0 else 1)
        if eggs_tab(texts):
            return
        base.tap_x(bounds, rest=1.5)
    if not eggs_tab(look()[1]):
        keep_capture("eggs")
        raise Stop("couldn't get back to the Eggs tab")


def to_map():
    """the Eggs tab's X goes to the map"""
    screen, texts, path, bounds = look()
    if screen in ("list", "tag-tab") or eggs_tab(texts):
        base.tap_x(bounds)
    screen = base.settle(look, lambda g: g[0] in ("map", "mainmenu"), timeout=8)[0]
    if screen not in ("map", "mainmenu"):
        log(f"  not sure it's on the map ({screen}); leaving the game as it is")


def fill_and_time():
    """on the Eggs tab: the best free egg into the ∞ incubator (if it's free), then the hatch timer (see 1. and 2.)"""
    have, bounds = read_eggs()
    log("eggs: " + said(have))
    free = [e for e in have if not e[2]]
    if free:
        best = max(free, key=lambda e: (e[1], -have.index(e)))
        if incubate(best, bounds):
            have = base.settle(lambda: read_eggs()[0], lambda h: sum(e[2] for e in h) > sum(e[2] for e in have),
                               timeout=4)
            log("eggs now: " + said(have))
    left = [k - w for w, k, i, _ in have if i]
    if left:
        km = max(0.0, min(left))
        minutes = max(MIN_MINUTES, MIN_PER_KM * km)
        log(f"next hatch run in {minutes:.0f} min ({km:g} km left), at {timer.later('hatch', minutes)}")
    elif free:
        log(f"next hatch run in {RETRY_MINUTES} min (no egg went in), at {timer.later('hatch', RETRY_MINUTES)}")
    else:
        timer.off("hatch")
        log("next hatch run: none, no egg is incubating (timer off)")


def check():
    """from the map: the Eggs tab, fill_and_time, and back to the map"""
    if not ui.ANDROID:
        raise Stop("the egg check works on the Pixel only (POGO_PHONE=android)")
    log("checking the eggs")
    to_eggs()
    fill_and_time()
    to_map()
