#!/usr/bin/env python3
"""/hatch: hatch the eggs that are ready, put the best egg in the free ∞ incubator, and set the timer for the next
run. The Pixel only, on whichever trainer is signed in.

  POGO_PHONE=android python3 skills/hatch/hatch.py
  pogo.py hatch

1. The game is started fresh (closed, then opened). An already open game held a ready egg on the map for 1.5 min
   and never hatched it; a fresh start showed the egg's "Oh?" 17 s in (2026-11-13).
2. Each "Oh?" gets a tap. Its rewards (Stardust, Candy) go by themselves. The hatched Pokémon's page gets its X,
   which opens the Eggs tab. No "Oh?" within WAIT_HATCH s on the map: the Eggs tab is opened by hand.
3. On the Eggs tab each egg reads "walked / km". A teal label is an egg in an incubator. The egg with the most km
   that isn't in one is opened, INCUBATE, and the ∞ incubator is taken only if it's free: the picker's first slot
   with no "N USE" under it. A paid incubator (1, 2 or 3 uses) is never tapped (the user, 2026-11-13).
4. The next run: max(15, 7 x the km left) minutes from now, read off the incubated egg that has the least left.
   The km shown is what's left to walk, bonus and all (a 10 km egg showed "0 / 5 km" during a half-distance bonus:
   35 min, the user, 2026-11-13). Nothing incubating: the timer goes off.
5. Its X back to the map. The game stays open; the phone is locked.

The timer is skills/shared/timer.py. Log in runs/<time>-android/log.txt.
"""
import os, re, sys, time
from PIL import Image

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log, keep_capture
import home, session, popups, timer

WAIT_HATCH = 25  # seconds on the map with no "Oh?" before it opens the eggs itself (the "Oh?" came 8 s after the map)
LOAD_TIMEOUT = 150  # seconds for the open, the hatches and the Eggs tab
OH = (0.5, 0.6)  # a tap anywhere on the "Oh?" screen goes on
EGG_ABOVE = 0.06  # an egg sits this far above its "walked / km" label
INFINITE = (0.145, 0.77)  # the incubator picker's first slot: the ∞ one when it's free
FREE_SLOT_X = 0.25  # a "N USE" label left of this is under the first slot: the ∞ is busy, that slot is a paid one
TEAL_MIN = 15  # teal pixels in a label that make it an incubating egg's (2026-11-13: 46 and 85 teal, the rest 0)
MIN_PER_KM, MIN_MINUTES = 7, 15  # the user's rule: 7 min a km, 15 at least (a 2 km egg)
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


# ---------- the steps ----------

def open_fresh():
    """the game closed and opened again, so it checks the eggs (see 1.)"""
    a = ui.android
    if a.PKG in a.shell("dumpsys activity activities | grep -E 'ResumedActivity'"):
        log("closing the game, so it opens fresh and checks the eggs")
        a.shell(f"am force-stop {a.PKG}")
        time.sleep(1.0)
    home.android_launch()
    try:
        a.ready(force=True)
    except a.NotReady as e:
        raise Stop(str(e))


def through_hatches():
    """from the opening game to the Eggs tab (through the hatches) or the map. -> ('eggs' or 'map', hatched)"""
    end = time.time() + LOAD_TIMEOUT
    hatched, on_map, prev, same = 0, None, None, 0
    while time.time() < end:
        screen, texts, path, bounds = look()
        if eggs_tab(texts):
            return "eggs", hatched
        if oh(texts):
            hatched += 1
            log(f"an egg is hatching ({hatched}): tapping its 'Oh?'")
            base.click(*OH, bounds, fuzz=0.02, rest=2.0)
            on_map = None
            continue
        if popups.clear(texts, bounds):
            continue
        if screen == "detail":  # the hatched Pokémon: its X opens the Eggs tab
            log(f"  {'hatched' if hatched else 'a Pokémon page is open, closing it'}: "
                f"{ui.summary([t for t in texts if 0.07 < t[1] < 0.3], 60)}")
            base.tap_x(bounds, rest=2.0)
            continue
        if screen == "map":
            on_map = on_map or time.time()
            if time.time() > on_map + WAIT_HATCH:
                return "map", hatched
        else:
            on_map = None
            if screen == "unknown":  # loading, rewards going by, or a box: one that sits still gets unstick
                words = sorted(t[4] for t in texts)
                same = same + 1 if words == prev else 0
                prev = words
                if same >= 6:
                    same = 0
                    home.unstick(texts)
        time.sleep(0.8)
    keep_capture("hatch")
    raise Stop(f"no Eggs tab or map in {LOAD_TIMEOUT}s")


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
    uses = lambda ts: [x for x in ts if re.search(r"\bUSE\b", ui.norm(x[4]))]
    _, texts, _, bounds = base.settle(look, lambda g: label(g[1], "INCUBATORS") and uses(g[1]), timeout=6)
    if not label(texts, "INCUBATORS"):
        keep_capture("picker")
        log(f"  the incubator picker didn't open: {ui.summary(texts, 80)}")
        leave_to_eggs()
        return False
    first = min((x[0] for x in uses(texts)), default=1.0)
    if first < FREE_SLOT_X:
        log("  the ∞ incubator is busy (only paid ones in the picker): leaving it")
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


def script():
    t0 = time.time()
    session.ready()
    if not ui.ANDROID:
        raise Stop("hatch runs on the Pixel only: POGO_PHONE=android")
    open_fresh()
    where, hatched = through_hatches()
    log(f"hatched {hatched} egg{'s' * (hatched != 1)}" if hatched else "no egg hatched")
    if where != "eggs":
        to_eggs()
    have, bounds = read_eggs()
    log("eggs: " + ", ".join(f"{w:g}/{k:g}{' (incubating)' if i else ''}" for w, k, i, _ in have))
    free = [e for e in have if not e[2]]
    if free:
        best = max(free, key=lambda e: (e[1], -have.index(e)))
        if incubate(best, bounds):
            have = base.settle(lambda: read_eggs()[0], lambda h: sum(e[2] for e in h) > sum(e[2] for e in have),
                               timeout=4)
            log("eggs now: " + ", ".join(f"{w:g}/{k:g}{' (incubating)' if i else ''}" for w, k, i, _ in have))
    left = [k - w for w, k, i, _ in have if i]
    if left:
        km = max(0.0, min(left))
        minutes = max(MIN_MINUTES, MIN_PER_KM * km)
        log(f"next run in {minutes:.0f} min ({km:g} km left), at {timer.later('hatch', minutes)}")
    else:
        timer.off("hatch")
        log("next run: none, no egg is incubating (timer off)")
    to_map()
    log(f"done: {hatched} hatched, {time.time() - t0:.0f}s")


def main():
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="android" if ui.ANDROID else "iphone")
    session.main(script)


if __name__ == "__main__":
    main()
