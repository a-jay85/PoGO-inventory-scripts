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

import ui
import base
from base import Stop, log, keep_capture
import search, session, popups, pages, pokedb

STORAGE = ("list", "tag-tab", "detail", "menu", "appraisal", "appraise-intro", "gym")
OPEN = ("detail", "menu", "appraisal", "appraise-intro", "gym")  # a Pokémon open: back_to_list() closes it
LOAD_TIMEOUT = 150  # seconds for the game to open and get past its loading screens
MAX_BACKS = 12  # Back presses (Android) on screens it doesn't know before it gives up
IOS_OPEN_TRIES = 3  # iPhone: tries at opening the game from the home screen before it gives up
APP_NAME = "Pokemon GO"  # iPhone: typed into Spotlight, whose Top Hit is then the game wherever its icon sits
PILL = (0.5, 0.84)  # iPhone: the home screen's Search pill, if its text isn't read


def main_menu(texts):
    return {"POKDEX", "POKMON", "ITEMS", "SHOP"} <= {ui.norm(t[4]).replace("É", "") for t in texts}


def home_search(texts):
    """iPhone: the home screen's own 'Q Search' pill, bottom middle just above the dock. The game never has text
    there (its search bar is at the top; the keyboard's search key is at the right). Goes by text, so a new event
    icon for the game (2026-11-01: purple and orange, no red top) doesn't hide the home screen"""
    return any(ui.norm(t[4]).lstrip("Q ").strip() == "SEARCH" and 0.75 < t[1] < 0.9 and 0.4 < t[0] + t[2] / 2 < 0.6
               for t in texts)


def spotlight(texts):
    """iPhone: Spotlight is open (its 'Top Hit' heading). A run left there counts as the home screen"""
    return any(ui.norm(t[4]) == "TOP HIT" for t in texts)


def top_hit(texts):
    """iPhone: Spotlight's Top Hit, upper case (the row just under the 'Top Hit' heading), None if none.
    Pokémon HOME can be in the same list, so only an exact POKÉMON GO opens anything"""
    head = next((t for t in texts if ui.norm(t[4]) == "TOP HIT"), None)
    if not head:
        return None
    below = [t for t in texts if head[1] + head[3] < t[1] < head[1] + 0.2]
    return ui.norm(min(below, key=lambda t: t[1])[4]).replace("POKMON", "POKEMON") if below else None


def splash(texts):
    """the game's loading picture ('SCOPELY  The Pokémon Company' at the bottom): Back there closes the game
    (2026-10-28), so it's waited out"""
    return "POKÉMON COMPANY" in ui.joined(texts) or "POKEMON COMPANY" in ui.joined(texts)


def where(path, texts):
    """the screens start() cares about: a storage screen, tags/rename, map, mainmenu, exit, signin, anr, ios-home,
    mirroring, blank, unknown"""
    if not ui.ANDROID and (home_search(texts) or spotlight(texts)):
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
    got = base.look(where)
    note_storage(got[1])
    return got


def note_storage(texts):
    limit = storage_limit(texts)
    if limit is not None:
        SEEN_LIMIT.update(n=limit, twice=limit == SEEN_LIMIT["n"])
        if SEEN_LIMIT["twice"] and by_storage(limit):
            pokedb.set_account(by_storage(limit), sure=False)


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


def android_restart():
    """force-stop the Pixel's game and open it again. A game left running for hours can stop taking taps while its
    page looks normal (/trade's dead spells, PR #311; 2026-11-09 /ivc: 16 h up, no X or tag tap took for 4 min)"""
    a = ui.android
    log("  the game takes no taps: restarting it")
    a.shell(f"am force-stop {a.PKG}")
    time.sleep(1.0)
    android_launch()


def keyboard_up():
    return "mInputShown=true" in ui.android.shell("dumpsys input_method | grep mInputShown=")


def iphone_open():
    """the game in front on the iPhone, wherever its icon sits (dock, any page, a folder, the App Library):
    iPhone Mirroring's cmd+1 goes to the home screen, its Search pill opens Spotlight, 'Pokemon GO' typed there
    makes the game the Top Hit, and Return opens it (or brings it back where it was). Return is only pressed when
    the Top Hit reads POKÉMON GO. -> True if it pressed Return"""
    base.key("1", cmd=True)
    _, texts, _, bounds = base.settle(look, lambda got: home_search(got[1]), timeout=4)
    pill = next((t for t in texts if home_search([t])), None)
    if pill:
        base.tap_box(pill, bounds)
    else:
        base.click(*PILL, bounds)
    base.settle(look, lambda got: not home_search(got[1]), timeout=3)  # the pill goes when Spotlight opens
    base.key("a", cmd=True)  # (a query left from last time would get the name added to it)
    base.key("delete")
    base.type_text(APP_NAME)
    hit = top_hit(base.settle(look, lambda got: top_hit(got[1]) == "POKEMON GO", timeout=4)[1])
    if hit != "POKEMON GO":
        log(f"  Spotlight's Top Hit is {hit!r}, not Pokémon GO: back to the home screen")
        base.key("1", cmd=True)
        return False
    base.key("return")
    return True


# ---------- start ----------

backs, reopened = 0, False  # this run's steps out of screens nobody knows
banner_seen = 0  # when unstick started waiting on the gift banner that's up now
BANNER_WAIT = 15  # seconds a gift banner gets to go away before its screen counts as unknown
HATCH_SCREENS = 40  # seconds after an egg's "Oh?" when an unknown screen is its rewards, its Pokémon or the eggs


scopely_taps = 0  # this run's taps on Scopely Explore's 'Return to Pokémon GO'
SCOPELY_TRIES = 3


def leave_scopely(texts):
    """the Scopely Explore page (the profile's EXPLORE button opens it): Back does nothing there, its 'Return to
    Pokémon GO' link at the top goes back to the game. On the Pixel the link sits under the status bar: the tap goes
    just below that (2026-11-03). -> True if it tapped"""
    global scopely_taps
    hit = next((t for t in texts if ui.scopely([t])), None)
    if not hit:
        return False
    if scopely_taps >= SCOPELY_TRIES:
        keep_capture("start")
        raise Stop("on the Scopely Explore page and 'Return to Pokémon GO' doesn't close it: tap it by hand")
    scopely_taps += 1
    log("  on the Scopely Explore page: tapping 'Return to Pokémon GO'")
    bounds = ui.capture()[1]
    fx = hit[0] + hit[2] * random.uniform(0.4, 0.6)
    fy = hit[1] + hit[3] * random.uniform(0.4, 0.6)
    if ui.ANDROID:  # the link's text sits under the Pixel's status bar (top 98 px), which takes the tap: just
        fy = max(fy, (random.randint(118, 142) - bounds[1]) / bounds[3])  # below it still opens it (y 137, 2026-11-03)
    base.click(fx, fy, bounds)  # (bounds are phone pixels with the adb capture)
    time.sleep(2.5)
    return True


def unstick(texts):
    """one step out of a screen the scripts don't know. A box popups.py knows gets its button first, then a
    screen pages.py knows (another script's) its way out. Then Android:
    Back. iPhone: the home screen and the game's icon, once. Raises Stop when out of steps. -> True if the game was
    (re)opened"""
    global backs, reopened, banner_seen
    seen = ui.summary(texts, 200)
    if ui.gift_banner(texts):  # it goes by itself, and the screen under it may be one everyone knows
        now = time.time()
        if now > banner_seen + 4 * BANNER_WAIT:
            banner_seen = now
            log(f"  a gift banner is up: waiting for it to go: {seen[:80]}")
        if now < banner_seen + BANNER_WAIT:
            time.sleep(2.0)
            return False
    bounds = ui.capture()[1]
    if popups.clear(texts, bounds):  # a box another script knows (a trade's late 'expired'...): its button
        return False
    if pages.step_out(texts, bounds):  # a whole screen another script knows (a trade's lobby, a gym...): its way out
        return False
    if leave_scopely(texts):
        return False
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
        base.tap_x(bounds)
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
    prev, same, unknowns, reconnected, hatched, home_taps, restarted = None, 0, 0, False, 0, 0, False
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
                    base.skip_intro(texts, path, bounds)
                base.back_to_list()  # the known-safe way out
                continue
            except Stop as e:  # not a storage Pokémon after all (a trade's result screen): out the other way
                log(f"  couldn't close the Pokémon the usual way: {e}")
                if ui.ANDROID and not restarted:  # its X took no tap at all: a stuck game, a restart fixes it
                    restarted = True
                    android_restart()
                    opened, t_open, end = True, time.time(), time.time() + LOAD_TIMEOUT
                    continue
                unstick(texts)
        elif screen in ("map", "mainmenu"):
            if not storage:
                return screen
            search.off_map()
            try:
                got = base.wait_for(*STORAGE, timeout=8)
                if got[0] == "list":  # opened from the map: at the top (seen on the iPhone, 2026-11-02)
                    search.scrolled = False
                    note_storage(got[1])  # the bar is empty only now: two reads here spare trainer() clearing it later
                    look()
                return got[0]
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
            if home_taps >= IOS_OPEN_TRIES:  # each tap gives LOAD_TIMEOUT again: without this it never ends
                keep_capture("start")  # (2026-11-01: 300 taps in 35 min, the game wouldn't open from any icon)
                raise Stop(f"tapped Pokémon GO on the iPhone's home screen {home_taps} times and it didn't open: "
                           f"open it once on the iPhone itself, then run again")
            home_taps += 1
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
        elif screen == "unknown" and popups.clear(texts, bounds):  # a box any script may meet (popups.py)
            pass
        elif screen == "unknown" and storage and "SEND GIFT" in ui.joined(texts):  # /trade and /gift can end here, and
            log("  on a friend's page: closing it")  # the iPhone has no Back key: the X, then the profile's X below
            base.tap_x(bounds)
            time.sleep(1.5)
        elif screen == "unknown" and storage and (profile(texts) or ui.profile_tabs(texts)):  # a stop or a reopen left
            log("  on the profile: closing it")  # the profile up (any of its tabs): its X
            base.tap_x(bounds)
            time.sleep(1.5)
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


def squash(s):
    """OCR mixes up I, l, 1 and | in names: one letter for all of them, spaces out"""
    return re.sub(r"[IL1|!]", "I", re.sub(r"\s+", "", s.upper()))


# which account, by the storage limit: HashTagAJay's 12900, CyrillJan's 7875. Under LEAST_STORAGE is a misread
BIG_STORAGE = 10_000, "HashTagAJay"
LEAST_STORAGE = 5_000
SEEN_LIMIT = {"n": None, "twice": False}  # the limit in the Pokémon screen's header, as look() last read it


def by_storage(limit):
    """the trainer a storage limit belongs to, or None if it can't be either's"""
    if limit >= BIG_STORAGE[0]:
        return BIG_STORAGE[1]
    return next(n for n in TRAINERS if n != BIG_STORAGE[1]) if limit >= LEAST_STORAGE else None


def forget_storage():
    """the account is changing"""
    SEEN_LIMIT.update(n=None, twice=False)
    pokedb.set_account(None)


def storage_limit(texts):
    """the Pokémon screens' header count 'N / LIMIT' (TAGS / POKÉMON / EGGS showing) -> LIMIT, or None"""
    if not {"TAGS", "EGGS"} <= {ui.norm(t[4]) for t in texts}:
        return None
    for t in texts:
        if m := re.search(r"\b\d[\d,]*\s*/\s*(\d{1,2},?\d{3})\b", t[4]):
            return int(m.group(1).replace(",", ""))
    return None


def profile(texts):
    """the profile's ME tab. A friend's banner ('... opened your Gifts!') can cover its tabs: then the trainer name
    with LEVEL and BUDDY under it tells it"""
    j = ui.joined(texts)
    if "FRIENDS" in j and ("TOTAL ACTIVITY" in j or "SCRAPBOOK" in j or "JOURNAL" in j):
        return True
    words = {ui.norm(t[4]) for t in texts}
    return {"LEVEL", "BUDDY"} <= words and any(squash(n) in squash(" ".join(t[4] for t in texts)) for n in TRAINERS)


def clipped_names(texts, below):
    """OCR can drop the last letter or two of a name that's all there ('HashTagAJa' for HashTagAJay, iPhone, 2026-11-10,
    on the profile under a gift banner and on /gift's ME tab): the trainers one line above `below` is the start of,
    all but those letters"""
    return [n for n in TRAINERS if any(len(n) - 2 <= len(w := squash(t[4])) < len(n) and squash(n).startswith(w)
                                       for t in texts if t[1] < below)]


def to_map():
    """from anywhere to the map -> its texts"""
    start(storage=False)
    for _ in range(10):
        screen, texts, path, bounds = look()
        if screen == "map":
            return texts
        if screen in STORAGE:
            start()  # the known way to the Pokémon list, then its X
            base.tap_x(base.look()[3])
        elif screen == "mainmenu":
            base.back_or_x(bounds)
        elif screen == "exit":  # Back on the map asks this
            press_text(texts, bounds, "CANCEL")
        else:
            unstick(texts)
        time.sleep(1.5)
    keep_capture("nomap")
    raise Stop("couldn't get to the map")


def trainer(fast=True):
    """the signed-in trainer's name. fast: the storage limit tells it, read twice the same. The header only shows it
    over an empty search ('Q (33)' over any other), so a look on the way in counts, and otherwise the bar gets cleared
    (ends on the Pokémon screen). Else read off the profile (ME tab) from the map, ending on the map. Starts anywhere"""
    if fast and not profile(look()[1]):  # (on the profile: the name is right there)
        start()
        cleared = False
        for _ in range(6):
            if SEEN_LIMIT["twice"]:
                who = by_storage(SEEN_LIMIT["n"])
                if who:
                    log(f"signed in: {who} (its {SEEN_LIMIT['n']} storage)")
                    pokedb.set_account(who)
                    return who
                break
            screen, texts, path, bounds = look()
            if storage_limit(texts) is None and not cleared and {"TAGS", "EGGS"} <= {ui.norm(t[4]) for t in texts}:
                search.clear_search()
                cleared = True
            elif storage_limit(texts) is None:
                time.sleep(0.5)
    start(storage=False)
    for _ in range(12):
        screen, texts, path, bounds = look()
        j = ui.joined(texts)
        if popups.clear(texts, bounds):
            continue
        if profile(texts):
            names = lambda tx: [n for n in TRAINERS if squash(n) in squash(" ".join(t[4] for t in tx))]
            got = names(texts)
            if len(got) != 1:  # the name may still be coming in ('HashTagAJa' under a gift banner, iPhone, 2026-11-10)
                texts = base.settle(lambda: look()[1], lambda tx: len(names(tx)) == 1, timeout=3)
                got = names(texts)
            if not got:
                got = clipped_names(texts, 0.3)
            if len(got) != 1:
                keep_capture("trainer")
                raise Stop(f"can't read the trainer name on the profile: {[t[4] for t in texts if t[1] < 0.3]}")
            log(f"signed in: {got[0]}")
            pokedb.set_account(got[0])
            base.tap_x(bounds)
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
        elif screen == "list" and not {"TAGS", "EGGS"} <= {ui.norm(t[4]) for t in texts}:
            base.to_tags_tab()  # a tag's list: its X isn't the Pokémon screen's (stuck 12 looks, 2026-11-02)
        elif screen in ("list", "tag-tab"):
            base.tap_x(bounds)
            time.sleep(1.5)
        elif screen == "mainmenu":
            base.back_or_x(bounds)
            time.sleep(1.5)
        elif screen == "exit":
            press_text(texts, bounds, "CANCEL")
            time.sleep(1.5)
        elif screen == "ios-home":  # the game went to the back (a laggy iPhone, 2026-11-02): open it again
            start(storage=False)
        else:
            unstick(texts)
            time.sleep(1.0)
    keep_capture("trainer")
    raise Stop("couldn't get to the profile to read the trainer name")


if __name__ == "__main__":
    base.new_run_dir(base.RUNS)
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
