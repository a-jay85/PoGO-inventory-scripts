#!/usr/bin/env python3
"""Start from anywhere: every script calls start() first, so the phone can be on any screen, or Pokémon GO not open.

- First session.ready(): iPhone Mirroring open and connected, or the Pixel awake and unlocked (its PIN from a file).
- Android: opens Pokémon GO if it isn't in front, waits out the loading screens, and presses Back
  on popups and on screens the scripts don't know until the map or the Pokémon screens show.
  Back on the map asks "exit Pokémon GO?": that's answered CANCEL.
- iPhone: brings iPhone Mirroring forward (opened again once if it loses the iPhone). On the iPhone's home screen, or a screen it doesn't know, it goes to the
  home screen and taps the game in the dock, which opens it or brings it back. No Back key there, so a popup it
  still doesn't know after that stops the run.
- A tag sheet or a nickname box left open by an earlier run: the nickname box is canceled (nothing saved). The tag
  sheet keeps the rule to_search_list() always had: DONE if something is ticked, stop if nothing is.
- start() ends on the Pokémon screens (list, Tags tab or a Pokémon), where to_top() and to_search_list() take over.
  start(storage=False) (for /trade): with the game already open it ends right there, on any screen (trade.py knows
  screens this doesn't). With the game just opened it ends on the map.

  POGO_PHONE=android python3 home.py             get to the Pokémon screens from wherever the phone is
  POGO_PHONE=android python3 home.py --trade     the same with start(storage=False): stop on any screen
  POGO_PHONE=android python3 home.py --trainer   only print the trainer name read off the profile
"""
import os, random, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))  # run.py (the tapper)
import ui
import run as base
from run import Stop, log, keep_capture
import search, session

STORAGE = ("list", "tag-tab", "detail", "menu", "appraisal", "appraise-intro", "gym")
OPEN = ("detail", "menu", "appraisal", "appraise-intro", "gym")  # a Pokémon open: back_to_list() closes it
LOAD_TIMEOUT = 150  # seconds for the game to open and get past its loading screens
MAX_BACKS = 12  # Back presses (Android) on screens it doesn't know before it gives up
DOCK = (0.73, 0.926)  # iPhone: the Poké Ball in the dock, third icon (Spotlight doesn't list the app near the top)


def main_menu(texts):
    return {"POKDEX", "POKMON", "ITEMS", "SHOP"} <= {ui.norm(t[4]).replace("É", "") for t in texts}


def dock_icon(path):
    """iPhone: the game's icon in the home screen's dock (red top, black band, white button). The home screen has no
    app names to read (labels hidden), and its weather widget reads as a search bar, so this goes before classify"""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = lambda fx, fy: im.getpixel((int(fx * W), int(fy * H)))
    red = [px(DOCK[0] + dx, 0.91) for dx in (-0.03, 0.03)]
    white = [px(DOCK[0] + dx, 0.945) for dx in (-0.03, 0, 0.03)]
    return all(r > 200 and g < 120 and b < 90 for r, g, b in red) and min(px(DOCK[0], 0.93)) > 230 \
        and all(min(p) > 200 for p in white)


def splash(texts):
    """the game's loading picture ('SCOPELY  The Pokémon Company' at the bottom): Back there closes the game
    (2026-10-28), so it's waited out"""
    return "POKÉMON COMPANY" in ui.joined(texts) or "POKEMON COMPANY" in ui.joined(texts)


def passenger(texts, bounds):
    """'You're going too fast!' (the phone moving): tap I'M A PASSENGER -> True if it was up. OCR runs the words
    together ('I'M APASSENGER', 2026-10-28)"""
    if "TOO FAST" not in ui.joined(texts):
        return False
    hit = next((t for t in texts if "PASSENGER" in ui.up(t)), None)
    if not hit:
        return False
    log("  'going too fast' popup: tapping I'M A PASSENGER")
    base.tap_box(hit, bounds)
    time.sleep(1.5)
    return True


def where(path, texts):
    """the screens start() cares about: a storage screen, tags/rename, map, mainmenu, exit, signin, anr, ios-home,
    mirroring, blank, unknown"""
    if not ui.ANDROID and dock_icon(path):
        return "ios-home"
    screen = ui.classify(texts)
    if screen != "unknown":
        return screen
    j = ui.joined(texts)
    if splash(texts):
        return "blank"
    if "EXIT POK" in j:
        return "exit"  # Android: "Do you want to exit Pokémon GO?"
    if "RETURNING PLAYER" in j or "NEW PLAYER" in j or "SIGN IN WITH" in j:
        return "signin"
    if "ISN'T RESPONDING" in j or "KEEPS STOPPING" in j:
        return "anr"
    if not ui.ANDROID and "CONNECTING" in j:
        return "blank"  # iPhone Mirroring on its way to the iPhone
    if not ui.ANDROID and any(w in j for w in session.TROUBLE):
        return "mirroring"  # iPhone Mirroring can't reach the phone
    if main_menu(texts):
        return "mainmenu"
    if len(texts) <= 12 and search.pokeball(path):
        return "map"
    if all(t[1] < 0.08 for t in texts):
        return "blank"  # only the status bar (or nothing): the game is loading
    return "unknown"


def look():
    return base.look(where)


def press_text(texts, bounds, word):
    """tap a button by its label (exit dialog's CANCEL: not a target ui.plan knows)"""
    hit = next((t for t in texts if ui.norm(t[4]) == word), None)
    if not hit:
        return False
    base.tap_box(hit, bounds)
    return True


# ---------- getting the game in front ----------

def android_launch():
    """Pokémon GO the app in front (opened if it wasn't). session.ready() has woken and unlocked the phone.
    True if it had to open it."""
    a = ui.android
    if a.PKG in a.shell("dumpsys activity activities | grep -E 'ResumedActivity'"):
        return False
    log("Pokémon GO isn't in front: opening it")
    a.shell(f"monkey -p {a.PKG} -c android.intent.category.LAUNCHER 1")
    for i in range(40):  # a cold start takes a few seconds to put the game in front
        time.sleep(1)
        if a.PKG in a.shell("dumpsys activity activities | grep -E 'ResumedActivity'"):
            return True
        if i == 15:  # (right after a Back closed it, the first launch can go nowhere: 2026-10-28)
            a.shell(f"monkey -p {a.PKG} -c android.intent.category.LAUNCHER 1")
    raise Stop("opened Pokémon GO but it never came to the front")


def keyboard_up():
    return "mInputShown=true" in ui.android.shell("dumpsys input_method | grep mInputShown=")


def iphone_open():
    """iPhone Mirroring's own shortcut cmd+1 goes to the home screen, then the game's icon in the dock: opens the
    game, or brings it back where it was"""
    base.key("1", cmd=True)
    time.sleep(1.5)
    base.click(*DOCK, ui.capture()[1], spaced=False)  # (front() first, as before; no tap gap, but it counts as a tap)


# ---------- start ----------

backs, reopened = 0, False  # this run's steps out of screens nobody knows
HATCH_SCREENS = 40  # seconds after an egg's "Oh?" when an unknown screen is its rewards, its Pokémon or the eggs


def unstick(texts):
    """one step out of a screen the scripts don't know. Android: Back. iPhone: the home screen and the game's icon,
    once. Raises Stop when out of steps. -> True if the game was (re)opened"""
    global backs, reopened
    seen = ui.summary(texts, 200)
    if ui.ANDROID:
        if not reopened and android_launch():  # the phone's home screen (the game went to the back): Back won't help
            reopened = True
            return True
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


def through_hatch(texts, bounds, hatched):
    """one step through an egg hatching (on the way to the map): its 'Oh?' gets a tap, the screens after it (its
    Pokémon's page, the eggs) an X. hatched: when the last 'Oh?' was seen (0: never). -> the new hatched time when a
    step was taken, None when this unknown screen is neither"""
    if any(t[4].strip() == "Oh?" for t in texts):
        log("  an egg is hatching: tapping through it")
        hatched = time.time()
        search.click(0.5 + random.uniform(-0.02, 0.02), 0.6 + random.uniform(-0.02, 0.02), bounds)
        time.sleep(2.0)
        return hatched
    if time.time() < hatched + HATCH_SCREENS or re.search(r"\b\d+(\.\d+)?\s*/\s*\d+\s*km\b",
                                                          " ".join(t[4] for t in texts)):
        log(f"  after the hatch: closing {ui.summary(texts, 60)}")
        search.click(*X_BUTTON, bounds)
        time.sleep(2.0)
        return hatched
    return None


def start(storage=True):
    """from wherever the phone is to the Pokémon screens. storage=False (/trade): the game open and loaded, on any
    screen it knows or trade.py might (friend page, trade lobby...). -> the screen it ended on"""
    session.ready()  # iPhone Mirroring open and connected, or the Pixel awake and unlocked
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
    prev, same, unknowns, reconnected, hatched = None, 0, 0, False, 0
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
            if search.leave_panel(texts, bounds) or search.leave_multiselect(texts, bounds):
                continue
            if ui.ANDROID and keyboard_up():  # typing into the bar left the keyboard over the list: Back hides it
                log("  the keyboard is up: hiding it")
                ui.android.key("back")
                time.sleep(1.0)
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
            if reconnected:
                raise Stop("iPhone Mirroring can't reach the iPhone: lock it and leave it alone, then run again")
            reconnected = True
            log("iPhone Mirroring lost the iPhone: opening it again")
            session.quit_mirroring()
            time.sleep(2.0)
            session.connect()
            end = time.time() + LOAD_TIMEOUT
        elif screen == "signin":
            keep_capture("signin")
            raise Stop("Pokémon GO wants you to sign in: do that by hand")
        elif screen == "anr":
            keep_capture("anr")
            raise Stop("the phone says Pokémon GO isn't responding: close it by hand")
        elif screen == "unknown" and passenger(texts, bounds):
            pass
        elif screen == "unknown" and (step := through_hatch(texts, bounds, hatched)) is not None:
            hatched = step
        elif screen == "unknown" and storage and search.sort_menu(texts):  # a stop left the sort menu up (a slow
            log("  the sort menu is open: closing it")                 # iPhone opened it after giving up)
            search.click(search.SORT_BUTTON[0], search.SORT_BUTTON[1], bounds)  # its X sits where the button was
            time.sleep(1.5)
        elif screen == "unknown" and storage and not ui.ANDROID and ui.search_panel(texts):  # left with the panel open
            search.leave_panel(texts, bounds)  # (an empty bar shows tags and Recommended, no tiles: no list)
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


# ---------- who's signed in ----------

TRAINERS = ("HashTagAJay", "CyrillJan")  # the user's two accounts
X_BUTTON = (0.5, 0.937)  # the round X at the bottom middle: closes the profile and the Pokémon list


def squash(s):
    """OCR mixes up I, l, 1 and | in names: one letter for all of them, spaces out"""
    return re.sub(r"[IL1|!]", "I", re.sub(r"\s+", "", s.upper()))


def trainer():
    """the signed-in trainer's name, read off the profile (ME tab) from the map. Starts anywhere, ends on the map"""
    start(storage=False)
    for _ in range(12):
        screen, texts, path, bounds = look()
        j = ui.joined(texts)
        if "FRIENDS" in j and ("TOTAL ACTIVITY" in j or "SCRAPBOOK" in j or "JOURNAL" in j):
            got = [n for n in TRAINERS if squash(n) in squash(" ".join(t[4] for t in texts))]
            if len(got) != 1:
                keep_capture("trainer")
                raise Stop(f"can't read the trainer name on the profile: {[t[4] for t in texts if t[1] < 0.3]}")
            log(f"signed in: {got[0]}")
            search.click(*X_BUTTON, bounds)
            time.sleep(1.5)
            return got[0]
        if "FRIENDS" in j and "ADD FRIEND" in j and press_text(texts, bounds, "ME"):  # the profile opens on its
            time.sleep(1.5)  # last tab: Friends after /gift
        elif ui.ANDROID and {"OK", "?123"} <= {t[4].strip().upper() for t in texts}:  # a run stopped while typing
            ui.android.key("back")  # (the keyboard and its own text box are up)
            time.sleep(1.0)
        elif ui.search_panel(texts):
            if ui.ANDROID:  # an empty bar has no (x): a tap there opens the keyboard again
                ui.android.key("back")
            else:
                search.close_panel(bounds)
            time.sleep(1.0)
        elif screen == "map":
            search.click(0.13, 0.91, bounds)  # the profile picture
            time.sleep(2.0)
        elif screen in OPEN:
            base.back_to_list()
        elif screen in ("list", "tag-tab"):
            search.click(*X_BUTTON, bounds)
            time.sleep(1.5)
        elif screen == "mainmenu":
            if ui.ANDROID:
                ui.android.key("back")
            else:  # no Back key: the menu's own X at the bottom middle
                search.click(*X_BUTTON, bounds)
            time.sleep(1.5)
        elif screen == "exit":
            press_text(texts, bounds, "CANCEL")
            time.sleep(1.5)
        else:
            unstick(texts)
            time.sleep(1.0)
    keep_capture("trainer")
    raise Stop("couldn't get to the profile to read the trainer name")


if __name__ == "__main__":
    base.new_run_dir(os.path.join(base.HERE, "runs"))
    if "--trainer" in sys.argv[1:]:
        try:
            print(trainer())
        except Stop as e:
            sys.exit(f"STOPPED: {e}")
        sys.exit(0)
    try:
        print(start("--trade" not in sys.argv[1:]))
    except Stop as e:
        sys.exit(f"STOPPED: {e}")
