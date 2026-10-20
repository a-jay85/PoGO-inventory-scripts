#!/usr/bin/env python3
"""Start from anywhere: every script calls start() first, so the phone can be on any screen, or Pokémon GO not open.

- Android: wakes the phone, opens Pokémon GO if it isn't in front, waits out the loading screens, and presses Back
  on popups and on screens the scripts don't know until the map or the Pokémon screens show.
  Back on the map asks "exit Pokémon GO?": that's answered CANCEL.
- iPhone: brings iPhone Mirroring forward. On the iPhone's home screen, or a screen it doesn't know, it goes to the
  home screen and taps the game in the dock, which opens it or brings it back. No Back key there, so a popup it
  still doesn't know after that stops the run.
- A tag sheet or a nickname box left open by an earlier run: the nickname box is canceled (nothing saved). The tag
  sheet keeps the rule to_search_list() always had: DONE if something is ticked, stop if nothing is.
- start() ends on the Pokémon screens (list, Tags tab or a Pokémon), where to_top() and to_search_list() take over.
  start(storage=False) (for /trade): with the game already open it ends right there, on any screen (trade.py knows
  screens this doesn't). With the game just opened it ends on the map.

  POGO_PHONE=android python3 home.py      get to the Pokémon screens from wherever the phone is
"""
import os, random, re, sys, time

import ui
import run as base
from run import Stop, log, keep_capture
import search

STORAGE = ("list", "tag-tab", "detail", "menu", "appraisal", "appraise-intro", "gym")
OPEN = ("detail", "menu", "appraisal", "appraise-intro", "gym")  # a Pokémon open: back_to_list() closes it
LOAD_TIMEOUT = 150  # seconds for the game to open and get past its loading screens
MAX_BACKS = 12  # Back presses (Android) on screens it doesn't know before it gives up
DOCK = (0.73, 0.926)  # iPhone: the Poké Ball in the dock, third icon (Spotlight doesn't list the app near the top)
IOS_APPS = {"SETTINGS", "APP STORE", "PHOTOS", "CAMERA", "SAFARI", "MAPS", "CLOCK", "CALENDAR", "WEATHER", "MESSAGES",
            "NOTES", "WALLET", "MAIL", "MUSIC", "FACETIME", "REMINDERS"}  # two of these: the iPhone's home screen


def joined(texts):
    return " ".join(t[4].upper() for t in texts)


def main_menu(texts):
    return {"POKDEX", "POKMON", "ITEMS", "SHOP"} <= {ui.norm(t[4]).replace("É", "") for t in texts}


def where(path, texts):
    """the screens start() cares about: a storage screen, tags/rename, map, mainmenu, exit, signin, anr, blank, unknown"""
    screen = ui.classify(texts)
    if screen != "unknown":
        return screen
    j = joined(texts)
    if "EXIT POK" in j:
        return "exit"  # Android: "Do you want to exit Pokémon GO?"
    if "RETURNING PLAYER" in j or "NEW PLAYER" in j or "SIGN IN WITH" in j:
        return "signin"
    if "ISN'T RESPONDING" in j or "KEEPS STOPPING" in j:
        return "anr"
    if not ui.ANDROID and ("IPHONE IN USE" in j or "IPHONE IS LOCKED" in j or "UNLOCK YOUR IPHONE" in j):
        return "mirroring"  # iPhone Mirroring can't reach the phone
    if not ui.ANDROID and len({ui.norm(t[4]) for t in texts} & IOS_APPS) >= 2:
        return "ios-home"
    if main_menu(texts):
        return "mainmenu"
    if len(texts) <= 12 and search.pokeball(path):
        return "map"
    if all(t[1] < 0.08 for t in texts):
        return "blank"  # only the status bar (or nothing): the game is loading
    return "unknown"


def look():
    path, bounds = ui.capture()
    texts = ui.ocr(path)
    ui.remember(path, texts, bounds)
    return where(path, texts), texts, path, bounds


def press_text(texts, bounds, word):
    """tap a button by its label (exit dialog's CANCEL: not a target ui.plan knows)"""
    hit = next((t for t in texts if ui.norm(t[4]) == word), None)
    if not hit:
        return False
    search.click(hit[0] + hit[2] / 2, hit[1] + hit[3] / 2, bounds)
    return True


# ---------- getting the game in front ----------

def android_launch():
    """phone awake and unlocked, Pokémon GO the app in front (opened if it wasn't). True if it had to open it."""
    a = ui.android
    if a.adb("get-state").strip() != "device":
        raise Stop("phone not connected: plug it in, turn on USB debugging, and tap Allow on the phone")
    if "mWakefulness=Awake" not in a.shell("dumpsys power | grep -m1 mWakefulness="):
        a.shell("input keyevent KEYCODE_WAKEUP")
        time.sleep(1.5)
    if re.search(r"mIsShowing=true", a.shell("dumpsys window | grep mIsShowing=")):
        a.shell("input keyevent KEYCODE_MENU")  # a lock screen with no PIN opens with this
        time.sleep(1.5)
        if re.search(r"mIsShowing=true", a.shell("dumpsys window | grep mIsShowing=")):
            raise Stop("the phone is locked: unlock it (turn on Stay awake in Developer options so it stays unlocked)")
    if a.PKG in a.shell("dumpsys activity activities | grep -E 'ResumedActivity'"):
        return False
    log("Pokémon GO isn't in front: opening it")
    a.shell(f"monkey -p {a.PKG} -c android.intent.category.LAUNCHER 1")
    for _ in range(15):  # a cold start takes a few seconds to put the game in front
        time.sleep(1)
        if a.PKG in a.shell("dumpsys activity activities | grep -E 'ResumedActivity'"):
            return True
    raise Stop("opened Pokémon GO but it never came to the front")


def iphone_open():
    """iPhone Mirroring's own shortcut cmd+1 goes to the home screen, then the game's icon in the dock: opens the
    game, or brings it back where it was"""
    base.key("1", cmd=True)
    time.sleep(1.5)
    bounds = ui.capture()[1]
    x, y = base.to_points(*DOCK, bounds)
    base.front()
    ui.sh(ui.HELPER, "click", f"{x:.1f}", f"{y:.1f}", str(ui.tap_ms()))


# ---------- start ----------

backs, reopened = 0, False  # this run's steps out of screens nobody knows


def unstick(texts):
    """one step out of a screen the scripts don't know. Android: Back. iPhone: the home screen and the game's icon,
    once. Raises Stop when out of steps. -> True if the game was (re)opened"""
    global backs, reopened
    seen = " | ".join(t[4] for t in texts)[:200]
    if ui.ANDROID:
        if backs >= MAX_BACKS:
            keep_capture("start")
            raise Stop(f"pressed Back {backs} times and still don't know this screen: {seen}")
        backs += 1
        log(f"  unknown screen, pressing Back: {seen[:120]}")
        ui.android.key("back")
        time.sleep(1.5)
        return False
    if reopened:
        keep_capture("start")
        raise Stop(f"don't know this screen (no Back key on the iPhone), close it by hand: {seen}")
    reopened = True
    log(f"  unknown screen, opening Pokémon GO from the home screen: {seen[:120]}")
    iphone_open()
    time.sleep(3)
    return True


def start(storage=True):
    """from wherever the phone is to the Pokémon screens. storage=False (/trade): the game open and loaded, on any
    screen it knows or trade.py might (friend page, trade lobby...). -> the screen it ended on"""
    opened = android_launch() if ui.ANDROID else False
    if ui.ANDROID:
        try:
            ui.android.ready(force=True)
        except ui.android.NotReady as e:
            raise Stop(str(e))
    else:
        base.front()
    t_open = time.time()
    end = t_open + LOAD_TIMEOUT
    prev, same, unknowns = None, 0, 0
    while True:
        try:
            screen, texts, path, bounds = look()
        except ui.Refused as e:  # window gone for a moment
            screen, texts = "blank", []
            log(f"  can't see the phone yet: {e}")
        if screen != "unknown":
            unknowns = 0
        if not storage and screen in STORAGE:
            return screen  # trade.py closes a trade's result screen itself
        if screen in ("list", "tag-tab"):
            if search.leave_panel(texts, bounds):
                continue
            return screen
        if screen in OPEN:
            try:
                if screen == "appraise-intro":
                    base.go("dialog", "appraisal")
                base.back_to_list()  # the known-safe way out
                continue
            except Stop as e:  # not a storage Pokémon after all (a trade's result screen): out the other way
                log(f"  couldn't close the Pokémon the usual way: {e}")
                unstick(texts)
        elif screen in ("map", "mainmenu"):
            if not storage:
                return screen
            search.off_map()
            try:
                return base.wait_for(*STORAGE, timeout=8)[0]
            except Stop:
                log("  the Pokémon list didn't open from the map: trying again")
        elif screen == "exit":  # Back on the map asks this: so it's the map under it
            if not (press_text(texts, bounds, "CANCEL") or press_text(texts, bounds, "NO")):
                unstick(texts)
                continue
            time.sleep(1.5)
            if not storage:
                return "map"
            # the map can carry too much text to be told apart (a banner): its Poké Ball opens the menu
            search.click(0.5 + random.uniform(-0.01, 0.01), 0.928 + random.uniform(-0.004, 0.004), ui.capture()[1])
            time.sleep(random.uniform(1.5, 2.0))
        elif screen == "rename":  # an earlier run cut off mid-name: nothing's saved until OK
            log("a nickname box was left open: canceling it")
            base.go("CANCEL", "detail")
        elif screen == "tags":
            search.to_search_list()  # its own rule for a tag sheet left open
            return base.look()[0]
        elif screen == "ios-home":
            log("on the iPhone's home screen: opening Pokémon GO")
            iphone_open()
            opened, t_open, end = True, time.time(), time.time() + LOAD_TIMEOUT
            time.sleep(3)
        elif screen == "mirroring":
            raise Stop("iPhone Mirroring can't reach the iPhone: lock it and leave it alone, then run again")
        elif screen == "signin":
            keep_capture("signin")
            raise Stop("Pokémon GO wants you to sign in: do that by hand")
        elif screen == "anr":
            keep_capture("anr")
            raise Stop("the phone says Pokémon GO isn't responding: close it by hand")
        elif screen == "unknown":
            if not storage and not opened:
                return screen  # the game was up already: trade.py knows screens this doesn't
            words = sorted(t[4] for t in texts)
            same = same + 1 if words == prev else 0
            prev, unknowns = words, unknowns + 1
            # just opened: wait out the loading screens (they sit still a while), then Back on a screen that stays
            # put three looks running. Already open: two unknown looks in a row is a popup or a screen nobody uses
            if (same >= 2 and time.time() > t_open + 20) if opened else unknowns >= 2:
                same = unknowns = 0
                if unstick(texts):
                    opened, t_open, end = True, time.time(), time.time() + LOAD_TIMEOUT
        if time.time() > end:
            keep_capture("start")
            raise Stop(f"couldn't get to the {'Pokémon screens' if storage else 'game'} in {LOAD_TIMEOUT}s "
                       f"(screen: {screen})")
        time.sleep(1.0)


if __name__ == "__main__":
    base.new_run_dir(os.path.join(base.HERE, "runs"))
    try:
        print(start("--trade" not in sys.argv[1:]))
    except Stop as e:
        sys.exit(f"STOPPED: {e}")
