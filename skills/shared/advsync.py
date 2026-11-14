#!/usr/bin/env python3
"""Turn Adventure Sync on for the account signed in. Pixel only. It never turns it off.

  POGO_PHONE=android python3 advsync.py           on, if it's off
  POGO_PHONE=android python3 advsync.py --look    only say whether it's on

account.py runs it at the end of every run, so whoever is signed in has Adventure Sync on. After it (and after a
run of this file, but not --look) comes the egg check (eggs.py): back on the map, the Pokémon screens' Eggs tab,
the mode's egg (shortest unless set, eggs.py) into the free ∞ incubator if it's empty, and the hatch timer set to 7 min a km left (8 min at least).

The way (the user, 2026-11-13): main menu (the map's Poké Ball) -> the Settings gear -> General -> Adventure Sync.
Learnt on the Pixel (2026-11-13):
- The switch sits at the right of the "Adventure Sync" row. Off: a grey track (about 219,224,224). On: a green one.
  A tap on a green switch turns it off, so it's tapped only when it reads grey.
- The tap has to land on the switch itself: a tap 0.017 of the screen below its middle did nothing, with no sign.
- Off -> on: a box "Enable Adventure Sync: Fitness ... TURN IT ON! / MAYBE LATER" -> TURN IT ON! -> a box "Adventure
  Sync Enabled. Congratulations! ..." -> OK -> the switch is green.
- The settings screens read as "list" to home.where, so home.start() can't leave them: Back goes out, to the map.
The game already had the phone's permissions (activity, location all the time). A screen asking for them would stop
the run with what it says.
"""
import os, sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
from PIL import Image

import ui
import base
from base import Stop, log, keep_capture
import home, account

SWITCH_X = (0.76, 0.97)  # where the switch can be across (window fractions)
SWITCH_DY = 0.02  # how far above and below the label's middle it's read
TAP_X = 0.87  # the switch's middle across
ENOUGH = 100  # pixels of one colour (of about 3000 read) to call it


def green(p):
    return p[1] - p[0] > 30 and p[1] > 180


def grey(p):
    return abs(p[0] - 219) < 10 and abs(p[1] - 224) < 10 and abs(p[2] - 224) < 10


def row(texts):
    """the "Adventure Sync" label's OCR box on the General screen, or None"""
    return next((t for t in texts if ui.up(t) == "ADVENTURE SYNC"), None)


def switch(path, t):
    """the switch beside label t: "on", "off" or None (not drawn yet)"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    y = t[1] + t[3] / 2
    box = im.crop((round(SWITCH_X[0] * W), round((y - SWITCH_DY) * H), round(SWITCH_X[1] * W),
                   round((y + SWITCH_DY) * H)))
    px = list(box.get_flattened_data())
    on, off = sum(map(green, px)), sum(map(grey, px))
    if on >= ENOUGH and on > off:
        return "on"
    if off >= ENOUGH:
        return "off"
    return None


def screen_of(texts):
    """the screens on the way: settings, general, enable (TURN IT ON!), enabled (OK), or account.screen_of's"""
    j = ui.joined(texts)
    if "TURN IT ON" in j:
        return "enable"
    if "ADVENTURE SYNC ENABLED" in j:
        return "enabled"
    words = {ui.up(t) for t in texts}
    if "GENERAL" in words and row(texts):
        return "general"
    return account.screen_of(texts)


def read_general():
    """look until the General screen's switch reads (a blank read may be the screen still drawing)"""
    def read():
        screen, texts, path, bounds = home.look()
        t = row(texts) if screen_of(texts) == "general" else None
        return texts, path, bounds, t, switch(path, t) if t else None
    return base.settle(read, lambda v: v[4] is not None, timeout=4)


def to_general():
    """from any screen to Settings > General"""
    home.start(storage=False)
    last, same = None, 0
    for _ in range(20):
        screen, texts, path, bounds = home.look()
        mine = screen_of(texts)
        if mine in ("general", "enable", "enabled"):
            return
        now = mine or screen
        same = same + 1 if now == last else 0
        last = now
        if same >= account.TRIES:
            keep_capture("advsync")
            raise Stop(f"stuck on {now} on the way to Settings > General: {ui.summary(texts, 150)}")
        if mine == "settings":
            log("  Settings: General")
            account.tap_text(texts, lambda s: s == "GENERAL", wait=2.0)
        elif screen == "mainmenu":
            log("  main menu: Settings")
            account.tap(*account.GEAR, wait=2.5)
        elif screen == "map":
            account.tap(*account.POKEBALL, wait=2.0)
        elif screen in home.STORAGE:  # (account.py's trainer read ends on the Pokémon list) its X goes to the map
            log("  Pokémon list: X")
            base.tap_x(bounds, rest=2.0)
        else:
            home.start(storage=False)
    keep_capture("advsync")
    raise Stop("couldn't get to Settings > General")


def leave():
    """Back out of the settings screens to the map"""
    for _ in range(5):
        ui.android.key("back")
        screen = base.settle(lambda: home.look()[0], lambda s: s == "map", timeout=2.5)
        if screen == "map":
            return
    home.start(storage=False)


def turn_on():
    """Adventure Sync on for whoever is signed in. -> True if it was off and is on now, False if it was on already"""
    if not ui.ANDROID:
        raise Stop("advsync.py works on the Pixel only (POGO_PHONE=android)")
    to_general()
    tapped = False
    for _ in range(8):
        screen, texts, path, bounds = home.look()
        mine = screen_of(texts)
        if mine == "enable":
            log("  Enable Adventure Sync: TURN IT ON!")
            hit = next(t for t in texts if "TURN IT ON" in ui.up(t))
            base.tap_box(hit, bounds, spread=0.15, rest=2.5)
            continue
        if mine == "enabled":
            log("  Adventure Sync Enabled: OK")
            hit = next((t for t in texts if ui.up(t) == "OK"), None)
            if not hit:
                keep_capture("advsync")
                raise Stop(f"the Adventure Sync Enabled box has no OK: {ui.summary(texts, 150)}")
            base.tap_box(hit, bounds, spread=0.15, rest=1.5)
            continue
        texts, path, bounds, t, state = read_general()
        if state == "on":
            log("Adventure Sync is on" + ("" if tapped else " already"))
            leave()
            return tapped
        if state is None:
            keep_capture("advsync")
            raise Stop(f"can't read the Adventure Sync switch: {ui.summary(texts, 150)}")
        if tapped:  # tapped once and the boxes didn't come: a second tap could be the one that turns it off
            def moved():
                screen, texts, path, bounds = home.look()
                t = row(texts)
                return screen_of(texts) in ("enable", "enabled") or bool(t and switch(path, t) == "on")
            if base.settle(moved, bool, timeout=5):
                continue
            keep_capture("advsync")
            raise Stop("tapped the Adventure Sync switch and it's still off, with no box: turn it on by hand")
        log("  Adventure Sync is off: tapping it on")
        base.click(TAP_X, t[1] + t[3] / 2, bounds, rest=2.5)
        tapped = True
    keep_capture("advsync")
    raise Stop("Adventure Sync didn't turn on")


def eggs():
    """the egg check after Adventure Sync (eggs.check): the free ∞ incubator filled, the hatch timer set"""
    import eggs as e
    e.check()


def look():
    if not ui.ANDROID:
        raise Stop("advsync.py works on the Pixel only (POGO_PHONE=android)")
    to_general()
    texts, path, bounds, t, state = read_general()
    leave()
    return state


if __name__ == "__main__":
    base.new_run_dir(base.RUNS)
    try:
        if "--look" in sys.argv[1:]:
            print(f"Adventure Sync: {look() or 'unread'}")
        else:
            print("Adventure Sync: turned on" if turn_on() else "Adventure Sync: on already")
            eggs()
    except Stop as e:
        sys.exit(f"STOPPED: {e}")
