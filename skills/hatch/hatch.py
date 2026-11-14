#!/usr/bin/env python3
"""/hatch: hatch the eggs that are ready, put the mode's egg in the free ∞ incubator, and set the timer for the next
run. The Pixel only, on whichever trainer is signed in.

  POGO_PHONE=android python3 skills/hatch/hatch.py [shortest|longest]
  pogo.py hatch [shortest|longest]

shortest (the default): the free egg with the fewest km goes in. longest: the one with the most km. The word is
saved (~/.config/pogo/hatch_mode), so the timer's runs and account.py's egg check keep it. No word: the saved mode.

1. The game goes to the back (the Home key), then opens again. An egg hatches when the game comes back from the
   home screen, once it has synced with the server and Adventure Sync's distance (the user, 2026-11-14). A game
   left in front held a ready egg on the map for 1.5 min and never hatched it (2026-11-13). The game isn't closed.
2. Each "Oh?" gets a tap. Its rewards (Stardust, Candy) go by themselves. The hatched Pokémon's page gets its X,
   which opens the Eggs tab. No "Oh?" within WAIT_HATCH s on the map: the Eggs tab is opened by hand.
3. The Eggs tab: the mode's egg into the free ∞ incubator, and the next run's time (skills/shared/eggs.py says how:
   7 min a km left, 8 min at least).
4. Its X back to the map. The game stays open; the phone is locked.

The timer is skills/shared/timer.py. Log in runs/<time>-android/log.txt.
"""
import os, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log, keep_capture
import home, session, popups, eggs
from eggs import oh, eggs_tab, look

WAIT_HATCH = 25  # seconds on the map with no "Oh?" before it opens the eggs itself (the "Oh?" came 8 s after the map)
LOAD_TIMEOUT = 150  # seconds for the open, the hatches and the Eggs tab
OH = (0.5, 0.6)  # a tap anywhere on the "Oh?" screen goes on


# ---------- the steps ----------

def open_fresh():
    """the game sent to the home screen and opened again, so it checks the eggs (see 1.)"""
    a = ui.android
    if a.PKG in a.shell("dumpsys activity activities | grep -E 'ResumedActivity'"):
        log("to the home screen and back, so the game checks the eggs")
        a.key("home")
        time.sleep(1.5)
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


def script():
    t0 = time.time()
    session.ready()
    if not ui.ANDROID:
        raise Stop("hatch runs on the Pixel only: POGO_PHONE=android")
    log(f"mode: the {eggs.mode()} free egg goes in")
    open_fresh()
    where, hatched = through_hatches()
    log(f"hatched {hatched} egg{'s' * (hatched != 1)}" if hatched else "no egg hatched")
    if where != "eggs":
        eggs.to_eggs()
    eggs.fill_and_time()
    eggs.to_map()
    log(f"done: {hatched} hatched, {time.time() - t0:.0f}s")


def main():
    words = [a for a in sys.argv[1:] if not a.startswith("-")]
    if words:
        if len(words) > 1 or words[0] not in eggs.MODES:
            sys.exit(f"hatch.py: one word, {' or '.join(eggs.MODES)} (got {' '.join(words)})")
        eggs.set_mode(words[0])
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="android" if ui.ANDROID else "iphone")
    session.main(script)


if __name__ == "__main__":
    main()
