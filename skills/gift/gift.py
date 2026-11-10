#!/usr/bin/env python3
"""/gift: send San Francisco gifts to every friend who can take one, the most useful first.

  caffeinate -dimsu python3 gift.py [--limit N]                       the iPhone
  POGO_PHONE=android caffeinate -dimsu python3 gift.py [--limit N]    the Android phone
  POGO_PHONE=both caffeinate -dimsu python3 gift.py [--limit N]       both phones at once
  [POGO_PHONE=android] python3 gift.py look                           what the script reads now; taps nothing
  add --dry-run: everything but SEND and the nickname's OK.
  add --dry-run --walk: a speed test that works after every gift is sent: each friend's page, always its friendship screen, no gift list.

HashTagAJay is on the iPhone (iPhone Mirroring: a touch on the Mac pauses it), CyrillJan on the Android phone (adb).
Each phone runs in its own process (ui.py keeps one phone's state in module globals).

Order: the "iii" search (no gift from me, not played with today) before "lll" (opened my gift or played with me
today). Inside each, the time zones farthest ahead first: lasia, leuro, latam, ea, ce, mo, then the rest. The list
is sorted "Can receive a gift", arrow down: friends who can take a gift come first, so the first row with the grey
already-sent badge ends that search. A friend with a Remote Trade sits on top whatever the sort, so their badge doesn't count.

Before each gift the friendship screen is checked. When the next heart is the 3rd, 4th or 5th, or it's the Forever
Friends bar: 1 point to go -> no gift, nickname "WAIT <old>"; 2 points -> gift, nickname "SENT <old>".
Only gifts from San Francisco are sent (the city line under the title), or from anywhere in California on an account in
CALIFORNIA. Never one with "lion", "tree" or "rock" in its title, and never with a sticker. When a phone has none left it stops; the other phone carries on. At the end the iPhone quits iPhone Mirroring and the Pixel locks.
Log and captures go in runs/<time>-<phone>/.

--limit N: at most N gifts per phone. --dry-run still taps the phone.
Whose account it is comes from the ME tab, once at the start. An unread one sends San Francisco gifts only. Each gift is
judged by the title and city on its own card, wherever it sits in the list. The preview must read the same before SEND.
Nicknames hold 12 characters: the space goes first, then letters off the end. One it can't type or read back is left
alone, and the log says to tag it by hand.
If Mirroring froze and the same preview is still there after the wait, it taps SEND once more, never a third time.
One friend never gets a gift from this script, on any account: NEVER_NAME / NEVER_NICK.
Take over mid-run and close the gift list, and it goes back to the friend list, searches again and goes on.

"interactable" resets at midnight, so an "iii" search that's finished stays finished for the day. It's remembered per
account in ~/.config/pogo/gift_iii_<trainer>.json, and later runs that day skip it. Finished means the list ran out (or
two searches read 0) with every friend dealt with. A grey SEND GIFT, a misread page, a lost screen, a raid, --limit,
no gifts left or a stop leave it unfinished, and so does --dry-run. An unread trainer name remembers nothing. "lll" is
always searched: friends move into it during the day. So is "iii" + rest: a friend just added has no zone yet, so that's
where they land. A friend with a zone who rejoins a finished "iii" search today (WAIT taken off) waits for midnight, or
delete that file.
"""
import argparse, difflib, json, os, random, re, subprocess, sys, time
from PIL import Image

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, keep_capture
import session, popups, pages
from search import nudge_bar

CITY = "SAN FRANCISCO"  # the only gifts sent: the rest (Chicago, North Carolina ...) are kept for sending by hand
KEEP = re.compile(r"\b(lion|tree|(?<!mission )rock)", re.I)  # San Francisco gifts that are kept anyway (Lions, Trees, Rocky too; Mission Rock is sent)
CALIFORNIA = {"HashTagAJay"}  # these accounts send any California gift. The rest send San Francisco gifts only
whole_state = False  # this phone's, picked once the friend list shows whose account it is
trainer = None  # this phone's account, read by whose(). None: unread, so no "iii" memory
NEVER = ("CHICAGO", "RALEIGH", "NORTH CAROLINA")  # cities never sent
FIRST = "!?&!$&!WAIT&!OPEN&interactable&!EGG&"  # iii: no gift from me yet, not played with today
THEN = "!WAIT&!OPEN&!interactable&!EGG&"  # lll: played with me today / opened my gift
ZONES = [  # farthest ahead of Pacific time first; "" (no zone) last picks up everyone else
    ("asia", "Japan:South Korea:Taiwan:Indonesia:Thailand:Singapore:Hong Kong&"),
    ("europe", "UK:Spain:Germany:Denmark:Sweden:France:Portugal:Norway:Poland:Italy:Netherlands&"),
    ("latam", "Brazil:Argentina:Chile:Atlantic:Peru&"),
    ("eastern", "ea"),
    ("central", "ce"),
    ("mountain", "mo"),
    ("rest", ""),
]
NICK_MAX = 12  # the game keeps the first 12 characters of a friend nickname
TYPEABLE = re.compile(r"[A-Za-z0-9 .,&!#+/*^=?$:;-]*")  # what the helper's keyboard (and adb) can type
SORT_BUTTON = (0.85, 0.935)
CLEAR_SEARCH = (0.86, 0.22)
HEART_Y = 0.384 if ui.ANDROID else 0.397  # the five big hearts on the friendship screen
HEART_X = (0.222, 0.362, 0.50, 0.64, 0.778) if ui.ANDROID else (0.234, 0.369, 0.505, 0.635, 0.768)
LEVELS = {"GOOD": 1, "GREAT": 2, "ULTRA": 3, "BEST": 4, "FOREVER": 5}  # ribbon -> hearts filled
WATCH_FROM = 2  # hearts index (0-based) from which a level-up is watched: the 3rd, 4th and 5th heart
HEART_NEAR = {2: 0.75, 3: 0.9, 4: 0.9, 5: 0.9}  # by hearts full: open the friendship screen only when the next one is this full
# (2026-11-07 layout, iPhone). 4th/5th heart: 8 to go read 97%, 20 read 67%, 74 read 18%. Forever bar: 18 read 80%, 56 read 38%
PHONE = "android" if ui.ANDROID else "ios"
DRY = False  # --dry-run: everything but SEND and the nickname box's OK
WALK = False  # --walk: a speed test on friends already gifted (see main)
typed = ""  # the last search typed: the box shows its end ('ea', 'mo')
LAG = 1 if ui.ANDROID else 2.5  # iPhone Mirroring now and then freezes for several seconds: wait longer there
PICKER_DRAG = (0.85, 0.25)  # a scroll down the gift list: long, to pass other cities fast, but no longer than the
# cards on screen (0.2-0.85) and no faster, so no card scrolls past between two looks
NEVER_NAME = "playharder"  # a friend who never gets a gift from this script, on any account (the user's rule): trainer
NEVER_NICK = "CPD"  # names start with this (the game shows playhardererer), or this nickname. Sent by hand only
MAX_LOST = 3  # lost screens in a row (each on a friend's page, backed out of) before the run stops


def log(msg):
    base.log(f"{PHONE:7} {msg}")  # the two phones print to the same terminal


class OutOfGifts(Exception):
    pass


# ---------- screen ----------

texts, path, bounds = [], None, None


def words():
    return {ui.norm(t[4]) for t in texts}


def joined():
    return " ".join(ui.up(t) for t in texts)


def find(pred):
    return [t for t in texts if pred(t)]


def label(name, lo=0.0, hi=1.0):
    hits = find(lambda t: ui.norm(t[4]) == name and lo <= t[1] <= hi)
    return hits[0] if hits else None


def menu_label(name):
    """a sort menu row's label, or None. Its round pick button sits right before it, and OCR can read that as a
    letter glued on ('OCAN RECEIVE A GIFT', 2026-11-07 Pixel: the run crashed on it)"""
    hits = find(lambda t: re.fullmatch(r"[OQCD]? ?" + re.escape(name), ui.norm(t[4])) is not None)
    return hits[0] if hits else None


def send_gift_label():
    """the SEND GIFT label's box, or None. OCR can tack a letter on ('SEND GIFTI') or glue the buttons beside it
    onto the same line ('SEND GIFTI  LOCAL  REMOTE  BATTLE', 2026-11-03 iPhone): then the box is cut to its SEND GIFT part"""
    for t in texts:
        if ui.is_label(t[4], "SEND GIFT"):
            return t
    for t in texts:
        m = re.match(r"\s*SEND GIFT\S*", t[4].upper())
        if m and len(t[4].rstrip()) > m.end():
            return (t[0], t[1], t[2] * m.end() / len(t[4].rstrip()), t[3], "SEND GIFT") + tuple(t[5:])
    return None


def summary():
    return ui.summary(texts)


def classify():
    j, w = joined(), words()
    for name, test in (("picker", pages.gift_picker), ("preview", pages.gift_preview), ("giftpopup", pages.gift_popup),
                       ("luckytrade", pages.lucky_trade), ("raid", pages.raid), ("buddy", pages.buddy),
                       ("trainercode", pages.trainer_code)):
        if test(texts):
            return name  # (pages.py has each one, so every script can leave it the way this one does)
    if "SET NICKNAME" in j and w & {"OK", "CANCEL"}:
        return "nickname"
    if pages.gift_list_scrolled(texts):
        return "picker"
    if pages.gift_sortmenu(texts):
        return "sortmenu"
    if pages.friend_page(texts):
        return "friend"
    if pages.friend_meter(texts):
        return "meter"
    if "EXIT POK" in j:
        return "exit"
    if "FRIENDS" in w and ("ME" in w or "SOCIAL" in w):
        if "TOTAL ACTIVITY" in j or "START DATE" in j or w & {"SCRAPBOOK", "JOURNAL", "GYM BADGES", "RECENTLY VISITED"}:
            # the ME tab: its trainer name sits where the search box would be. Scrolled down it still shows
            # the friend search's '(34)' under FRIENDS, and 'Start Date:' in the box's spot (2026-10-28)
            return "profile"
        if w & {"ADD FRIEND", "INVITE", "TRAINER NICKNAME"} or search_line() or count() is not None:
            return "friends"
        return "profile"
    from search import pokeball
    from home import splash
    if splash(texts):
        return "blank"  # the game still loading: wait, no Back
    if len(texts) <= 12 and path and pokeball(path):
        return "map"
    if all(t[1] < 0.08 for t in texts):
        return "blank"
    return "unknown"


def look():
    """run.look with gift's own screens, kept in the module globals texts/path/bounds (run.look writes steps.txt)"""
    global bounds

    def where(p, t):
        global texts, path
        texts, path = t, p  # classify() reads them
        return classify()

    s, _, _, bounds = base.look(where, remember=False)
    return s


def wait(*screens, timeout=10):
    """run.wait_for with gift's screens: a Refused look is raised, no capture kept (as gift always had it).
    Between looks: POLL on the iPhone, none on Android"""
    return base.wait_for(*screens, timeout=timeout, look=lambda: (look(), texts, path, bounds),
                         poll=base.poll_gap(POLL), catch=False, capture=False, detail=True)[0]


TAP_REST = (0.03, 0.08)  # after a tap: a moment only, as the wait after it looks for the next screen (was 0.25-0.4 s)
NAME_WAIT = 3.0  # seconds a friend page may take to show its trainer name
ICON_WAIT = 5.0  # seconds a friend the list shows as able to take a gift may take to colour their SEND GIFT icon
POLL = 0.1  # iPhone: seconds between two looks while waiting for a screen (a look takes 0.1-0.3 s; was 0.4)


def tap(fx, fy, fuzz=0.008, rest=None):
    """rest: seconds to wait after the tap (default TAP_REST)"""
    base.click(fx, fy, bounds, fuzz=fuzz, rest=TAP_REST if rest is None else rest)


def tap_text(t, dy=0.0, rest=None):
    base.tap_box(t, bounds, dy=dy, fuzz=min(0.008, t[2] / 4), rest=TAP_REST if rest is None else rest)


def tap_into(t, *screens, dy=0.0, timeout=8, on="friends"):
    """tap a word that opens another screen. iPhone Mirroring now and then drops a tap (the row lights up, or the
    button just sits there): when the screen is still `on`, with that word in the same spot, tap it again, twice at
    most. (A tap that only landed late at worst opens a gift's preview or a friend page: nothing is sent by it)"""
    for attempt in range(3):
        if attempt == 0 and t[1] > 0.25 and classify() == on and dimmed():  # (the capture t came from: no new look)  # (the tabs up top work under the veil)
            s = undim(*screens)  # (a tap on a greyed-out screen does nothing, or lands late)
            if s in screens:
                return s
        tap_text(t, dy=dy)
        try:
            return wait(*screens, timeout=timeout)
        except base.Lost:
            time.sleep(1.0)  # a fresh look: Mirroring's picture can freeze for a few seconds while the phone moved on
            s = look()
            if s in screens:
                return s
            if s == on and t[1] > 0.25 and dimmed():
                s = undim(*screens)
                if s in screens:
                    return s
            same = find(lambda u: clean(u[4]) == clean(t[4]) and abs(u[0] - t[0]) < 0.02 and abs(u[1] - t[1]) < 0.01)
            if attempt == 2 or s != on or not same:
                raise
            log(f"  tap on {t[4].strip()!r} didn't land: again")
            t = same[0]


def dimmed():
    """the last capture is greyed all over: the game is busy behind a dark veil (2026-11-02: 30 s after a gift,
    the friend list at grey 198 where it's white). Taps on it do nothing"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    ps = [im.getpixel((int(W * fx), int(H * fy))) for fx in (0.06, 0.94) for fy in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)]
    return all(180 <= p[0] <= 215 and max(p) - min(p) < 8 for p in ps)


def undim(*screens, timeout=45):
    """wait, without tapping, for the grey veil to lift -> the screen then"""
    log("  the screen is greyed out: waiting for it, no taps")
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(1.0)
        s = look()
        if s in screens or not dimmed():
            return s
    raise base.Lost(f"the screen stayed greyed out {timeout}s: {summary()}")


def drag(fy1, fy2, ms=500, x=None, settle=(0.7, 1.0)):
    """scroll by dragging from fy1 to fy2. x: where to grab (the gift list: the gap between its two columns, as a
    drag that starts on a card can land as a tap on it)"""
    x = x if x is not None else random.uniform(0.4, 0.6)
    base.drag(x, fy1, x + random.uniform(-0.005, 0.005), fy2, bounds, ms=ms, settle=settle,
              android_settle=base.LIST_SETTLE)


def close():
    """the X. No pause after it: every caller waits for the screen it opens (to_list won't X twice within 3 LAG)"""
    tap(*base.X_BUTTON, fuzz=0.004)  # (the preview's SEND sits just above: keep the X tap tight)


def close_popup(*screens, timeout=6, also=()):
    """X on a gift or Lucky Trade popup over a friend page -> one of the screens. The X can miss (a dropped tap, or
    the popup still sliding in): while the popup still shows, X again, twice at most. also: more screens whose X
    may be tapped again (only after the full wait and a fresh look still show them)"""
    for attempt in range(3):
        close()
        try:
            return wait(*screens, timeout=timeout)
        except base.Lost:
            time.sleep(1.0)  # a fresh look, as in tap_into
            s = look()
            if s in screens:
                return s
            if attempt == 2 or s not in ("giftpopup", "luckytrade", *also):
                raise
            log(f"  the {s} popup's X didn't land: again")


# ---------- the friend list ----------

def count():
    """the '(N)' under FRIENDS while a search is on"""
    for t in texts:
        m = re.fullmatch(r"\((\d[\d,]*)\)", t[4].strip())
        if m and t[1] < 0.14:
            return int(m.group(1).replace(",", ""))
    return None


def search_line():
    """the search box's text, when it's on screen (it scrolls away with the list)"""
    if any(0.18 < t[1] < 0.26 and ui.norm(t[4]) in ("ADD FRIEND", "INVITE") for t in texts):
        return None  # the button row: no search on, and under the picture sits the trainer's name or OFFLINE
    clear_x = any(0.18 < t[1] < 0.26 and t[0] > 0.75 and t[4].strip() in ("X", "x", "×") for t in texts)
    tail = lambda t: len(t[4].strip()) >= 2 and typed.lower().endswith(t[4].strip().lower())
    for t in texts:
        if 0.18 < t[1] < 0.26 and t[0] < 0.25 and ui.norm(t[4]) not in ("ADD FRIEND", "SEARCH", "INVITE", "OFFLINE") \
                and (re.search(r"[&!:?$]", t[4]) or ui.norm(t[4]) == "TRAINER NICKNAME" or clear_x or tail(t)):
            return t  # (a search has '&' '!' ':', or the X that clears it. At the list's bottom a friend's row sits here: a tap opens its gift)
    return None


MAX_BOUNCED = 6  # scrolls in a row that land off the list with no friend reached: stop, don't loop forever
REOPEN_LOAD = 45  # seconds the game gets to load after home.unstick reopened it (its loading tips read unknown)


def search_gone():
    """the friend list's button row under the picture (ADD FRIEND, INVITE) shows only with no search on. Passing
    through the map wipes the search (2026-11-03: a friend-row tap opened a raid): the whole list shows, unfiltered"""
    return any(0.18 < t[1] < 0.26 and ui.norm(t[4]) in ("ADD FRIEND", "INVITE") for t in texts)


def to_list():
    import home
    unknown, acted, end = 0, (None, 0.0), time.time() + 90
    loading, hatched = 0.0, 0.0  # loading: until when unknown screens are the game loading after a reopen
    while time.time() < end:
        s = look()
        if s == "friends":
            return
        if s == acted[0] and s != "unknown" and time.time() - acted[1] < 3 * LAG:
            time.sleep(POLL)  # the last tap hasn't shown yet: look again, don't tap twice
            continue
        unknown = unknown + 1 if s == "unknown" else 0
        acted = (s, time.time())
        if s == "profile" and find(lambda u: "SENT YOU A GIFT" in ui.up(u) or "DAYS AGO" in ui.up(u)):
            drag(0.35, 0.8, 350)  # the friend list, scrolled down past its search box: back up to it
        elif s == "profile":
            t = label("FRIENDS")
            tap_text(t) if t else tap(0.5, 0.09)
        elif s == "map":
            tap(0.13, 0.91)  # the profile picture
        elif s in ("friend", "meter", "picker", "preview", "giftpopup", "luckytrade", "trainercode", "buddy", "raid"):
            close()
        elif s == "nickname":
            cancel_nickname()
        elif s == "sortmenu":
            t = menu_label("CAN RECEIVE A GIFT")
            tap_text(t) if t else time.sleep(POLL)  # set_sort() checks the arrow after (unread: look again)
        elif s == "exit":
            t = label("CANCEL")
            tap_text(t) if t else time.sleep(POLL)
        elif s == "unknown" and popups.clear(texts, bounds):  # a box any script may meet (popups.py)
            unknown = 0
        elif s == "unknown" and (step := home.through_hatch(texts, bounds, hatched)) is not None:
            hatched, unknown = step, 0
        elif s == "unknown" and ui.classify(texts) in ("list", "tag-tab", "detail"):
            close()  # Pokémon storage: its X goes back to the map
        elif s == "unknown" and unknown > 2 and time.time() > loading:
            keep_capture("lost")
            if home.unstick(texts):  # (raises Stop when it's out of steps)
                loading = time.time() + REOPEN_LOAD  # the game reopened: wait out its loading screens
                end = max(end, loading + 30)
            unknown = 0
        time.sleep(POLL if s in ("friend", "meter", "giftpopup") else 0.5)  # (a friend page's X: the list comes fast)
    keep_capture("lost")
    raise Stop(f"couldn't get to the friend list: {summary()}")


def arrow():
    """the sort button's arrow: 'down' / 'up' / None"""
    return ui.sort_arrow(path, right_most=True)


SORT_ICON = os.path.join(HERE, "gift_sort_icon.png")  # the sort button's gift-and-arrow, green on teal (406 x 890 capture)
SORT_ICON_AT = (336, 813) if ui.ANDROID else (330, 815)  # its top left in the capture


def sorted_gift():
    """the sort button already shows Can receive a gift (the gift icon) -> its arrow 'down' / 'up', else None.
    Other sorts' icons and other screens read 0.4 or less"""
    return arrow() if (ui.icon_score(path, SORT_ICON, SORT_ICON_AT, slack=2) or 0) >= 0.6 else None


def set_sort():
    """Can receive a gift, arrow down. Picking the sort that's already on flips its arrow: pick, read, again.
    The sort button's picture shows when it's on already: nothing to tap, or one pick when only the arrow is up"""
    if look() == "friends":
        way = sorted_gift()
        if way == "down":
            log("already sorted Can receive a gift, arrow down")
            return
        if way == "up":
            log("sorted Can receive a gift, arrow up: picking it once to flip it")
    for attempt in range(4):
        if look() != "sortmenu":
            tap(*SORT_BUTTON, fuzz=0.004)
            wait("sortmenu", timeout=6 * LAG)
        t = menu_label("CAN RECEIVE A GIFT")
        if not t:
            log("the sort menu's Can receive a gift wasn't read: looking again")
            time.sleep(0.5)  # (the menu may still be sliding in)
            continue
        tap_text(t)
        time.sleep(1.2)
        if wait("friends", "sortmenu", timeout=6 * LAG) == "sortmenu":
            log("the sort menu is still open: picking again")
            continue  # (a lagging tap missed)
        way = arrow()
        if way == "down":
            log("sorted Can receive a gift, arrow down")
            return
        log(f"sort arrow reads {way}: again")
    keep_capture("sort")
    raise Stop("couldn't get the list sorted Can receive a gift, arrow down")


def sort_to_top():
    """a new sort puts the list back at its top, so this beats dragging up through hundreds of friends (the user's
    tip, 2026-11-07): pick Name, then set_sort() picks Can receive a gift again"""
    tap(*SORT_BUTTON, fuzz=0.004)
    wait("sortmenu", timeout=6 * LAG)
    name = menu_label("NAME")
    if name:
        tap_text(name)
        time.sleep(1.2)
        wait("friends", "sortmenu", timeout=6 * LAG)
    set_sort()  # (from the menu too, when Name wasn't read: the sort stays right, and the caller drags)


def to_top():
    global typed
    before, shortcut = None, True
    for _ in range(15):
        if look() != "friends":
            to_list()  # (a drag can land as a tap and open a friend's gift)
        if search_line() or label("SEARCH", 0.18, 0.28):
            return
        if shortcut:
            shortcut = False
            sort_to_top()
            continue
        rows_now = [r["name"] for r in rows()]
        box = [t for t in texts if 0.18 < t[1] < 0.26 and t[0] < 0.25 and len(t[4].strip()) >= 2]
        if rows_now == before and count() is not None and box:
            typed = box[0][4].strip()  # a scroll up moved nothing: the top, so this is the box (an older search's end, 'ea')
            return
        before = rows_now
        drag(0.35, 0.8, 350)
    raise Stop(f"couldn't scroll back to the search box: {summary()}")


def whole(box, q):
    """False when the box clearly holds less than the search: the box shows the last ~40 letters of a long
    search, so a short read (no '&' in it) is all there is. 2026-11-02: the 'iii' was lost and 'mo' alone ran"""
    t = ui.norm(box[4]).replace(" ", "").rstrip("X") if box else ""
    return not t or "&" in t or len(t) >= min(len(q), 20)


def box_end(box):
    """the search box's read, squeezed, without the clear X it can end with"""
    return ui.norm(box[4]).replace(" ", "").rstrip("X") if box else ""


def ends_zone(t, z):
    """t (box_end) ends with the short zone z. One letter of two may be misread: OCR read 'mo' as 'mg'. One stray
    l, I or | after it is the box's edge or cursor (2026-11-07: '&mo' read '&mol' four times and stopped the run)"""
    same = lambda t: len(t) >= len(z) and sum(a != b for a, b in zip(t[-len(z):], z.upper())) <= len(z) // 2
    return same(t) or (t[-1:] in ("L", "I", "|", "1") and same(t[:-1]))


def ends_query(t, q):
    """t (box_end) ends with the last letters of q: its short zone and the 3 letters before it ('EGG' + 'EA'), one
    misread allowed. 2026-11-10 iPhone: the box lost its last keys and read '...&interactable&!EG' (the eastern
    zone gone, 486 friends, not ~20). The zone alone passed: 'EG' is one letter off 'EA'. Then the swap to 'ce'
    left '...interactable&ce' with the '!EGG' gone, and that passed too"""
    want = ui.norm(q).replace(" ", "")
    want = want[-(len(ui.norm(q.rstrip("&").split("&")[-1]).replace(" ", "")) + 3):] if want else ""
    same = lambda t: len(t) >= len(want) and sum(a != b for a, b in zip(t[-len(want):], want)) <= 1
    return not want or same(t) or (t[-1:] in ("L", "I", "|", "1") and same(t[:-1]))


def commit_search():
    """the search is typed: commit it -> its result count, or None when none shows"""
    time.sleep(0.5)
    ok = None
    if ui.ANDROID:
        look()
        ok = find(lambda t: ui.norm(t[4]) == "OK" and t[0] > 0.75 and 0.5 < t[1] < 0.65)
    if ok:
        tap_text(ok[0])  # Android: the input strip's OK commits (Back would throw the text away)
    else:
        base.key("return")
    time.sleep(0.8)  # (then the result count is polled)
    for _ in range(8):
        if look() == "friends" and count() is not None:
            return count()
        time.sleep(0.5)
    box = search_line()
    if box and len(ui.norm(box[4])) > 12 and ui.norm(box[4]) != "TRAINER NICKNAME" \
            and not any(0.26 < t[1] < 0.85 for t in texts):
        return 0  # no one found: the list is empty and FRIENDS shows the total, with no '(0)'
    return None


LIST_LOAD = 25  # seconds the friend list gets to show its friends before a search


def list_loaded():
    """the friend list's header shows before its friends do. A search typed then finds nobody (2026-11-05: 'iii + asia'
    read 0, it's usually 34). No search is on here, so friends will come: wait for them -> False if none did"""
    t0 = time.time()
    while time.time() - t0 < LIST_LOAD:
        if look() == "friends" and rows():
            if time.time() - t0 > 1:
                log(f"  waited {time.time() - t0:.1f}s for the friend list to load")
            return True
        time.sleep(0.4)
    return False


def search(*parts):
    """type a search (its parts, joined) into the friend list -> its result count"""
    global typed
    q = "".join(parts)
    zeros = 0
    for attempt in range(4):
        to_top()
        box = search_line()
        if box and (ui.norm(box[4]) != "TRAINER NICKNAME" or not rows()):
            # (an empty box and no friends: a stopped search can leave this. They never load until the X: 2026-11-05)
            tap(*CLEAR_SEARCH, fuzz=0.004)
            time.sleep(1.0)
            look()
        if not list_loaded():
            keep_capture("noload")
            log(f"no friends on the list after {LIST_LOAD}s: trying again")
            continue
        s = label("SEARCH", 0.18, 0.28)
        if s:
            tap_text(s, dy=-0.035)
        else:
            tap(0.45, 0.22)  # an empty box ("Trainer Nickname")
        time.sleep(1.2)
        typed = q
        base.type_text(q)
        n = commit_search()
        if n is None:
            keep_capture("nocount")
            log(f"no result count after the search (the box reads {search_line()[4] if search_line() else None!r}): typing it again")
            continue
        box = search_line()
        log(f"  search box reads {box[4] if box else None!r}")
        # (2026-11-05: the box ended '!EGG' with the '&ea' lost: (514), not (46), so every zone went as one. whole() can't
        # see that, as the box still holds '&'. Only the short zones: OCR garbles the end of a long one)
        short = len(parts[-1]) <= 2  # (a short zone, or none: the box's end is all there, so it must be the query's)
        if not whole(box, q) or (box and short and not ends_query(box_end(box), q)):
            log(f"the box holds only part of {q!r}: typing it again")
            continue
        if rows():
            return n
        zeros += n == 0
        if zeros == 2:  # (typed whole twice, (0) twice, 2026-11-07: a real 0, and a long box can hide the nudge's A)
            log("  (0) again after typing it whole: nobody in this search")
            return 0
        n = rerun_search(n)  # (only a 0 after this is a real 0)
        if n is not None and (n == 0 or rows()):
            return n
        log(f"still ({n}) and no rows: typing it again")
    raise Stop(f"the search {q!r} didn't take after 4 tries: {summary()}")


def rerun_search(n):
    """a search typed too fast can land with the box right and the list blank: (n) or nothing at all. An A and a delete
    make the game run it again -> the count, or None when it needs typing again"""
    log(f"the search shows ({n}) and no rows: an A and a delete to run it again")
    box = search_line()
    tap_text(box) if box else tap(0.45, 0.22)
    time.sleep(1.2)
    nudged = nudge_bar(typed)
    n = commit_search()
    return n if nudged and whole(search_line(), typed) else None


def swap_zone(base_q, old, new):
    """the box holds base_q + a short zone ('ea') and nobody left in it can take a gift: delete just that zone
    and type the next ('ce', or nothing for the rest), rather than clearing the box and typing it all again
    -> the result count, or None when it didn't take (then search() does it the long way)"""
    global typed
    tail = typed[len(base_q):]
    if not typed.startswith(base_q) or tail.strip() != old:
        return None  # the box holds something else
    to_top()
    box = search_line()
    if not box or ui.norm(box[4]) == "TRAINER NICKNAME":
        return None
    tap_text(box)  # the cursor lands at the end (as for the ghost-rows space in search())
    time.sleep(1.2)
    for _ in tail:
        base.key("delete")
    if new:
        base.type_text(new)
    typed = base_q + new
    n = commit_search()
    box = search_line()
    t = box_end(box)
    log(f"  search box reads {box[4] if box else None!r}")
    took = (ends_query(t, typed) and not t.endswith(old.upper())) if new else \
        (not ends_zone(t, old) and ends_query(t, base_q))
    if n is None or not took or not whole(box, typed):
        log(f"swapping {old!r} for {new!r} didn't take: typing the search again")
        return None
    if not rows():
        n = rerun_search(n)
        if n is None or (n and not rows()):
            return None
    return n


def clean(name):
    return re.sub(r"[^A-Za-z0-9]+$", "", re.sub(r"^[^A-Za-z0-9]+", "", name.strip()))


def grey(p):
    return 135 <= p[0] <= 200 and abs(p[0] - p[1]) < 10 and abs(p[1] - p[2]) < 10


def badged(im, name_y):
    """the grey circle with a white arrow at the avatar's bottom right: a gift already sent, nothing more to send"""
    W, H = im.size
    for cy in range(int(H * (name_y + 0.03)), min(H - 7, int(H * (name_y + 0.10)))):
        for cx in range(int(W * .17), int(W * .25)):
            if min(im.getpixel((cx, cy))) < 220:
                continue
            for d in (6, 5):
                if all(grey(im.getpixel((cx + dx, cy + dy))) for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d))):
                    return True
    return False


def rows():
    """the rows on screen, top down: {name, t, badged}. A row is the trainer name at x ~0.29, the nickname just
    under it; rows too low to see their badge are left for the next scroll. Lines from 0.15 down are paired, so a
    row whose name sits just above 0.26 keeps its nickname: else the nickname reads as a name, with that row's
    badge under it, and the search ends there"""
    col = sorted((t for t in texts if 0.26 < t[0] < 0.32 and 0.15 < t[1] < 0.85 and t[4].strip()
                  and not re.search(r"SENT YOU|TRADE REQUEST|REMOTE TRADE|^REQUEST\.$", ui.up(t).strip())), key=lambda t: t[1])  # ('<name> sent you a Lucky Remote Trade request.', three lines)
    out, last = [], None
    for t in col:
        if last is not None and t[1] - last[1] < 0.035:
            if out and out[-1][0] is last:
                out[-1][1] = t[4].strip()  # the nickname line under the name
            continue
        last = t
        if len(clean(t[4])) >= 3:
            out.append([t, ""])
    im = Image.open(path).convert("RGB")
    trade = lambda t: any("REMOTE TRADE" in ui.up(o) and 0 < o[1] - t[1] < 0.1 for o in texts)
    return [{"name": clean(t[4]), "nick": nick, "t": t, "badged": badged(im, t[1]), "trade": trade(t)}
            for t, nick in out if t[1] > 0.26]


def name_key(s):
    """a trainer name with the letters OCR mixes up made the same"""
    return re.sub(r"[il1|Iİı]", "l", re.sub(r"[oO0]", "0", clean(s).replace("&", "8"))).lower()


def same_name(a, b):
    """the row's name and the page's: OCR reads them a little differently ('lycбo' / 'lyc60'). One letter off is ok"""
    a, b = name_key(a), name_key(b)
    return a == b or len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1


def never_gift(name, nick):
    """the friend the script must leave alone. Either read is enough: a friend skipped by mistake costs nothing"""
    bare = re.sub(r"^(WAIT|SENT)\s*", "", (nick or "").strip().strip('"“”').strip(), flags=re.I)
    return name_key(name or "").startswith(name_key(NEVER_NAME)) or bare.upper() == NEVER_NICK


# ---------- one friend ----------

def page_name():
    top = [t for t in texts if 0.07 < t[1] < 0.16 and t[0] < 0.25 and '"' not in t[4]
           and re.fullmatch(r"[\w&|]{3,}", clean(t[4]))]  # (below the status bar's clock; OCR reads an 8 as &: "Gr&estGuyEver",
    # an l as |: "dulces|79")
    return clean(sorted(top, key=lambda t: t[1])[0][4]) if top else None


def page_nickname():
    """the nickname under the name, in straight quotes -> (text, its line) / ("", None) when there's none"""
    for t in sorted(texts, key=lambda t: t[1]):
        if t[1] < 0.2 and t[0] < 0.25 and re.match(r'^["“”]', t[4].strip()):
            return t[4].strip().strip('"“”').strip(), t
    return "", None


def gift_icon(t):
    """the SEND GIFT icon above its label: coloured (yellow box) = a gift can go; grey = sent already"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    x0, x1 = int((t[0] + t[2] / 2 - 0.05) * W), int((t[0] + t[2] / 2 + 0.05) * W)
    y0, y1 = int((t[1] - 0.075) * H), int((t[1] - 0.005) * H)
    yellow = sum(1 for x in range(x0, x1) for y in range(y0, y1)
                 if (lambda p: p[0] > 200 and p[1] > 150 and p[2] < 110)(im.getpixel((x, y))))
    return yellow > 20


def send_button(t, p=None):
    """the preview's SEND button pixels (every 3rd), around its label t"""
    im = Image.open(p or path).convert("RGB")
    W, H = im.size
    cx, cy = (t[0] + t[2] / 2) * W, (t[1] + t[3] / 2) * H
    return [im.getpixel((x, y)) for x in range(int(cx - 0.1 * W), int(cx + 0.1 * W), 3)
            for y in range(int(cy - 0.02 * H), int(cy + 0.02 * H), 3)]


def sent_away(t, before):
    """after the SEND tap: captures (no OCR, for speed) until the SEND button changes. False if it never does"""
    end = time.time() + 8 * LAG
    while time.time() < end:
        p, _ = ui.capture()
        now = send_button(t, p)
        diff = sum(abs(a - b) for u, v in zip(before, now) for a, b in zip(u, v)) / (3 * len(now))
        if diff > 20:
            return True
    return False


def ribbon():
    return pages.ribbon(texts)


def points_text():
    j = joined()
    m = re.search(r"EARN (\d+) MORE FRIENDSHIP POINT", j)
    return int(m.group(1)) if m else None


def hearts_spot():
    """-> (x of the first heart's centre, y of the row, 0-1), measured from the FRIENDSHIP LEVEL label above the hearts, or None"""
    lab = next((t for t in texts if "FRIENDSHIP LEV" in ui.up(t)), None)
    return (lab[0] + 0.028, lab[1] + 0.0304) if lab else None


def forever_fill(im, W, H, cy):
    """a Forever Friend's bar right of the one heart -> (5, how full, 0-1), or None when there's no bar.
    It fills orange from the left over grey; each step is about 90 points"""
    def kind(r, g, b):
        if r > 220 and 90 < g < 225 and b < r - 50:
            return "O"
        if abs(r - g) < 14 and abs(g - b) < 14 and 140 < r < 235:
            return "g"
        return "."

    best = None
    for y in range(cy - 4, cy + 5):
        line = "".join(kind(*im.getpixel((x, y))) for x in range(int(W * 0.45), int(W * 0.95)))
        for run in re.split(r"\.{2,}", line):  # (one stray pixel inside the bar is fine)
            if len(run) > 0.2 * W and (best is None or len(run) > len(best)):
                best = run
    if best is None:
        return None
    return 5, best.count("O") / (best.count("O") + best.count("g"))


def heart_fill():
    """the five hearts right of Level on the friend page -> (hearts full, how full the next one is, 0-1), or None when
    they can't be read. A full heart has a red ring. The next one's ring fills orange from the left, over grey.
    A Forever Friend has one heart, then a bar"""
    spot = hearts_spot()
    if not spot:
        return None
    im = Image.open(path).convert("RGB")
    W, H = im.size
    cy = round(spot[1] * H)
    bar = forever_fill(im, W, H, cy)
    if bar:
        return bar
    r = round(0.032 * W)
    fill = []
    for i in range(5):
        cx = round((spot[0] + i * 0.0644) * W)
        red = orange = grey = 0
        for x in range(cx - r, cx + r + 1):
            for y in range(cy - r, cy + r + 1):
                p = im.getpixel((x, y))
                if p[0] > 220 and p[1] < 140 and p[2] < p[0] - 60:
                    red += 1
                elif p[0] > 220 and 140 <= p[1] < 225 and p[2] < p[0] - 50:
                    orange += 1
                elif abs(p[0] - p[1]) < 14 and abs(p[1] - p[2]) < 14 and 150 < p[0] < 235:
                    grey += 1
        if red + orange + grey < 150:
            return None  # no ring where a heart should be: the friendship screen can say
        fill.append((red >= 100, orange / (orange + grey) if orange + grey else 0))
    full = next((i for i, (is_red, _) in enumerate(fill) if not is_red), 5)
    return full, (fill[full][1] if full < 5 else 1.0)


def poll_until(ok, timeout):
    """look every POLL seconds until ok() -> True, or False once timeout seconds have passed"""
    end = time.time() + timeout
    while True:
        look()
        if ok():
            return True
        if time.time() >= end:
            return False
        time.sleep(POLL)


meter_spot = None  # which kind of spot opened the friendship screen last: tried first next time
hearts_kept = 0  # captures kept of a friend page whose hearts didn't read (a few a run, to see why)


def meter():
    """-> friendship points to the next level when that level is the 3rd, 4th or 5th heart or the Forever bar,
    else None (a level-up there doesn't matter). Leaves the friend page showing again"""
    global meter_spot, hearts_kept
    hf = heart_fill()
    if hf and (hf[0] < WATCH_FROM or hf[1] < HEART_NEAR[hf[0]]) and not WALK:  # (5 full hearts read 100%: always opened)
        log(f"  {hf[0]} hearts + {hf[1]:.0%} of the next: no level-up close, friendship screen not opened")
        return None
    if not hf and hearts_kept < 3:
        hearts_kept += 1
        keep_capture("hearts")
    spot = hearts_spot()
    nick, line = page_nickname()
    spots = [("heart", (spot[0] + 2 * 0.0644, spot[1]))] if spot else []  # the third heart
    spots += [("nick", (0.12, line[1] + line[3] / 2))] if line else []
    spots += [("top", (0.15, 0.177)), ("top2", (0.15, 0.204))]
    spots.sort(key=lambda k: k[0] != meter_spot)  # (the one that worked last time first)
    for kind, (fx, fy) in spots:
        tap(fx, fy, fuzz=0.004)
        try:
            wait("meter", timeout=4)
            meter_spot = kind
            break
        except Stop:
            if look() != "friend":
                close()
    else:
        keep_capture("meter")
        raise base.Lost(f"the friendship screen didn't open: {summary()}")  # (no gift yet: back to the list, as above)
    poll_until(lambda: ribbon() or points_text() is not None, 1.0)  # (still sliding in: wait() caught it early)
    level = ribbon()
    n = points_text()  # the Forever Friends bar shows its points with no tap
    if n is None and level != "GOOD":
        start = LEVELS[level] if level in LEVELS and LEVELS[level] >= WATCH_FROM else WATCH_FROM
        if level not in LEVELS and hf and WATCH_FROM <= hf[0] < 5:
            start = hf[0]  # (the ribbon unread: the small hearts say which one is next. Each wrong heart cost ~1 s)
        for i in range(start, 5):
            tap(HEART_X[i], HEART_Y, fuzz=0.004)
            poll_until(lambda: points_text() is not None, 1.0)
            n = points_text()
            if n is not None:
                break  # (counts from now, so a later heart's number is bigger: the first one is the next level)
    seen = f" (small hearts read {hf[0]} + {hf[1]:.0%})" if hf else " (small hearts not read)"
    log(f"  {level or '?'} friend, {n if n is not None else '-'} points to the next watched level{seen}")
    close()
    wait("friend", timeout=6)
    return n


def title_block(t, lines, left=False):
    """t and the lines under it in the same column (centred in the picker, left-aligned on the preview) -> (title, city), when t starts a gift's title. The
    title can wrap onto a second line; the city line ('San Francisco, CA, United') is the first one with a comma"""
    x = (lambda u: u[0]) if left else (lambda u: u[0] + u[2] / 2)
    col = sorted((u for u in lines if abs(x(u) - x(t)) < (0.03 if left else 0.08)), key=lambda u: u[1])
    if any(0 < t[1] - u[1] < 0.035 for u in col):
        return None, None  # t is the second line of a title, or the city's 'States'
    if any(0 < t[1] - u[1] < 0.035 and u[0] <= x(t) <= u[0] + u[2] for u in lines):
        return None, None  # the same, under one line OCR ran across both cards ('Olive My Love, Olive My Directional Bike Route at')
    block, y = [t], t[1]
    for u in col:
        if 0 < u[1] - y < 0.035:
            block.append(u)
            y = u[1]
    for i, u in enumerate(block[1:4], 1):
        if "," in u[4]:
            return " ".join(v[4].strip() for v in block[:i]), u[4].strip()
    return None, None


def in_california(city):
    """the state is the city line's second part: 'Fremont, CA, United' or 'Fremont, California,' (OCR: 'Califomia')"""
    parts = [p.strip() for p in city.upper().split(",")]
    return len(parts) > 1 and (parts[1] == "CA" or parts[1].startswith("CALIF")) and not any(n in parts[0] for n in NEVER)


def ours(title, city):
    if not title or KEEP.search(title):
        return False
    return city.upper().startswith(CITY) or (whole_state and in_california(city))


def near(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.9  # (a letter misread: 'Lot Al')


def picker_cards():
    """the gift list's cards on screen, in its order (row by row, left then right) -> [(title, city, its first line)]"""
    found = []
    for t in texts:
        if t[1] > 0.12:
            title, city = title_block(t, texts)
            if title:
                found.append((title, city or "", t))
    found.sort(key=lambda c: c[2][1])
    rows_ = []
    for c in found:
        if rows_ and c[2][1] - rows_[-1][0][2][1] < 0.02:
            rows_[-1].append(c)
        else:
            rows_.append([c])
    return [c for r in rows_ for c in sorted(r, key=lambda c: c[2][0])]


def preview_ok(title):
    """the preview reads 'Greetings from' / the title / the city"""
    lines = sorted(texts, key=lambda t: t[1])
    for i, t in enumerate(lines):
        if "GREETINGS FROM" in ui.up(t):
            # (only 'Greetings from''s column: words printed on the postcard photo sit to its left, 'JACK LONDON')
            rest = [u for u in lines[i + 1:] if u[1] - t[1] < 0.15 and abs(u[0] - t[0]) < 0.03]
            got, city = title_block(rest[0], rest, left=True) if rest else (None, None)
            cut = title.rstrip(".… ")  # the picker cuts a long title short ('Modern spiral chandeli')
            same = got is not None and (near(got, title) or (len(cut) >= 10 and near(got[:len(cut)], cut)))
            return same and ours(got, city or "") and ours(title, city or ""), got
    return False, None


picker_drags = 0  # scrolls down the gift list the last gift took: ours sit at the same place next time


def layout():
    """where the gift list's city lines sit. OCR reads a title a little differently each look ('better tagether'),
    the lines' places don't move unless the list does"""
    return [u[1] for u in sorted(texts, key=lambda u: u[1]) if u[1] > 0.2 and "," in u[4]]


def same_list(a, b):
    """a, b: (layout(), the words) of two looks -> the same view of the gift list"""
    return a is not None and len(a[0]) == len(b[0]) and all(abs(x - y) <= 0.012 for x, y in zip(a[0], b[0])) \
        and difflib.SequenceMatcher(None, a[1], b[1]).ratio() > 0.8


restarted_game = False  # this run restarted a Pixel game that took no SEND taps (once a run)


def send_gift():
    """from the friend page: picker -> one of our two gifts -> SEND. Raises OutOfGifts when neither is there"""
    global restarted_game
    global picker_drags
    t = send_gift_label()
    if not t:  # (not read on this look: the page may still be drawing it)
        t = base.settle(lambda: (look(), send_gift_label())[1], bool, timeout=3)
    if not t:
        raise Stop(f"no SEND GIFT on the friend page: {summary()}")
    tap_into(t, "picker", dy=-0.04, on="friend")
    blind = max(0, picker_drags - 1)  # where the last gift was found, less one scroll (a sent gift can shift the list up)
    drags = 0
    retaps = 0  # taps on a postcard that didn't open it (at most 2 a send)
    seen, dragged = None, None  # seen: the last look's layout; dragged: the layout and titles when it last scrolled
    for i in range(200):  # (about 3 looks a scroll: the first look after one still catches the list moving)
        if drags >= 60:  # (a full bag is a long list: 12 scrolls weren't enough on 2026-10-26)
            break
        if i:  # (the first pass reads the capture wait() just took)
            time.sleep(0.6)
            look()
        cards = []
        for title, city, t in picker_cards():
            if ours(title, city) and t[1] > 0.2 and t[1] - 0.11 > 0.18:
                cards.append((title, t))
        if cards:
            picker_drags = drags
            title, t = cards[0]
            tap(t[0] + t[2] / 2, t[1] - 0.11)  # the postcard above its title
            try:
                wait("preview", timeout=6 * LAG)
            except base.Lost:
                if retaps >= 2 or classify() != "picker":
                    raise
                retaps += 1  # (the list was likely still moving: the tap missed)
                log(f"  the tap on {title!r} didn't open it: looking again")
                continue
            ok, got = preview_ok(title)
            if not ok:  # (caught mid-animation: looks for 1.5 s more)
                poll_until(lambda: classify() == "preview" and preview_ok(title)[0], 1.5)
                ok, got = preview_ok(title)
            if not ok and got and retaps < 2:
                # (the list was still moving: the tap opened the card next to it, 2026-11-07 'Mission Creek Park'
                # for 'Mission Walk'). Back to the list, nothing sent, and look again
                keep_capture("preview")
                retaps += 1
                log(f"  the tap on {title!r} opened {got!r}: back to the list, looking again")
                close()
                wait("picker", timeout=6 * LAG)
                continue
            if not ok:
                keep_capture("preview")
                close()
                raise Stop(f"the gift preview reads {got!r}, wanted {title!r}: nothing sent")
            title = got  # (the full title, when the picker cut it short)
            if find(lambda u: "STICKER" in ui.up(u) and u[1] < 0.7):
                keep_capture("sticker")
                close()
                raise Stop("a sticker seems attached: nothing sent")
            send = label("SEND", 0.78, 0.9)
            if not send:
                # (a toast can slide over SEND for a few seconds: '2 Pass Tasks Updated' left 'SEN', 2026-11-10
                # Pixel). Look again until it slides away, no taps
                send = base.settle(lambda: look() == "preview" and label("SEND", 0.78, 0.9), bool, timeout=6)
                if send:
                    log("  SEND was covered: found it once the screen cleared")
            if not send:
                raise Stop(f"no SEND on the preview: {summary()}")
            if DRY:
                log(f"  DRY RUN: would SEND {title}")
                close()
                wait("picker", timeout=6)
                close()
                wait("friend", timeout=6)
                return title
            button = send_button(send)
            for tries in range(2):
                tap_text(send, rest=0)
                if sent_away(send, button):  # SEND is gone and the gift flies off: an X right now skips the animation
                    tap(*base.X_BUTTON, fuzz=0.004, rest=0)
                with base.changing("sending a gift"):  # (the gift may be gone: a lost screen stops the run, no retry)
                    s = wait("friend", "picker", "preview", "unknown", "blank", timeout=8 * LAG)
                for _ in range(int(10 * LAG)):
                    if s == "friend":
                        return title
                    time.sleep(0.6)
                    s = look()
                # iPhone Mirroring now and then drops the SEND tap (2026-11-02). The same preview after the full
                # wait, its SEND untouched: tap it once more (the user's call). Never a third time
                again = label("SEND", 0.78, 0.9)
                untouched = s == "preview" and again and preview_ok(title)[0] and abs(again[1] - send[1]) <= 0.01 \
                    and sum(abs(a - b) for u, v in zip(button, send_button(again))
                            for a, b in zip(u, v)) / (3 * len(button)) <= 20
                if tries or not untouched:
                    break
                keep_capture("send_again")
                log(f"  SEND on {title!r} didn't land: the same preview after the full wait, tapping it once more")
                send = again
            keep_capture("after_send")
            if ui.ANDROID and untouched and not restarted_game:
                # two SEND taps on the Pixel, both untouched: a game up for hours that takes no taps while its page
                # looks normal (2026-11-10: up 3.5 h, PR #311's dead spell). Nothing went. Restart it once a run, then
                # run_searches goes back to the list and tries this friend once more (a gift that went after all
                # reads grey there, and a friend takes one gift a day)
                restarted_game = True
                import home
                log("  the game takes no taps: restarting it")
                ui.android.shell(f"am force-stop {ui.android.PKG}")
                time.sleep(1.0)
                home.start(storage=False)  # (opens it and waits out its loading screens)
                raise base.Lost(f"two SEND taps on {title!r} didn't land: restarted the game")
            raise Stop(f"after SEND the screen is {s}: {summary()}")
        if classify() != "picker":
            # (the user took over and closed it, or a tap went astray. No SEND was tapped: run_searches goes back to the
            # list and tries this friend once more. One the user gifted by hand reads grey by then)
            keep_capture("not_picker")
            raise base.Lost(f"left the gift list while looking for our gifts: {summary()}")
        here = layout(), " ".join(u[4] for u in sorted(texts, key=lambda u: u[1]) if u[1] > 0.2)
        if not same_list(seen, here):
            seen = here  # still loading or still moving: look again before scrolling
            continue
        if same_list(dragged, here):
            if blind:  # (the scrolls without a look went past ours?) once more from the top
                log("  no gift of ours below the remembered spot: looking from the top")
                picker_drags = 0
                close()
                wait("friend", timeout=6 * LAG)
                return send_gift()
            close()  # a scroll moved nothing: the end of the gifts, and none of ours
            raise OutOfGifts()
        dragged = here
        if drags == 0 and blind:  # the list has loaded: scroll down to where the last gift was, no looks between
            for _ in range(blind - 1):
                drag(*PICKER_DRAG, x=0.5 + random.uniform(-0.005, 0.005))
            drags = blind - 1
            dragged = None  # (these scrolls weren't checked: the next one mustn't read as the list's end)
        drag(*PICKER_DRAG, x=0.5 + random.uniform(-0.005, 0.005))
        drags += 1
    raise Stop(f"scrolled the gift list {drags} times without reaching its end")


def is_tagged(tag, nick):
    """the nickname already reads new_nickname(tag, ...) of itself: renaming it would change nothing"""
    f = lambda x: re.sub(r"\s", "", x).lower()
    return bool(nick) and f(new_nickname(tag, nick)) == f(nick)


def new_nickname(tag, old):
    old = re.sub(r"^(WAIT|SENT)\s*", "", old)  # tagged on an earlier day: swap the tag, don't stack them
    if not old:
        return tag
    s = f"{tag} {old}"
    return s if len(s) <= NICK_MAX else (tag + old)[:NICK_MAX]


def cancel_nickname():
    if not label("CANCEL"):
        if ui.ANDROID:
            ui.android.key("back")  # hides the keyboard; CANCEL shows under it
        time.sleep(1)
        look()
    c = label("CANCEL")
    if c:
        tap_text(c)
        time.sleep(1)


def rename(tag, old, listed):
    """listed: the nickname as the friend list showed it. The box opens empty, so the old nickname is typed back
    from what was read: both reads must agree, or a misread would wipe the user's zone tag"""
    if re.sub(r"\s", "", old) != re.sub(r"\s", "", listed):  # (the list's OCR drops spaces: 'WAITLocal')
        log(f"  the nickname reads {old!r} on the page, {listed!r} in the list: tag it {tag} by hand")
        return False
    new = new_nickname(tag, old)
    if not TYPEABLE.fullmatch(new):
        log(f"  can't type nickname {new!r}: rename it to {tag} by hand")
        return False
    for _ in range(4):
        t = label("SET NICKNAME", 0.3, 0.95)
        if t:
            break
        drag(0.75, 0.3)
        look()
    else:
        raise Stop(f"no SET NICKNAME on the friend page: {summary()}")
    tap_text(t)  # (REMOVE FRIEND is right under it: the label itself, never below)
    wait("nickname", timeout=6)
    tap(0.5, 0.455, fuzz=0.004)
    time.sleep(0.6)
    base.key("a", cmd=True)
    base.key("delete")
    base.type_text(new)
    time.sleep(0.6)
    look()
    if ui.ANDROID:
        ok = find(lambda t: ui.norm(t[4]) == "OK" and t[0] > 0.75)
        if ok:
            tap_text(ok[0])  # the input strip's OK: back to the dialog with the text kept
            time.sleep(1)
            look()
    field = [t for t in texts if 0.42 < t[1] < 0.5 and "NICKNAME" not in ui.up(t)]
    got = field[0][4].strip() if field else ""
    if re.sub(r"\s", "", got).lower() != re.sub(r"\s", "", new).lower():
        keep_capture("nickname")
        cancel_nickname()
        log(f"  the nickname box reads {got!r}, wanted {new!r}: canceled, rename it to {tag} by hand")
        return False
    ok = label("OK", 0.5, 0.6)
    cancel = label("CANCEL", 0.55, 0.7)
    if not ok and cancel:  # OCR misses the OK (white on green) on the Android: it sits 0.073 above CANCEL
        ok = (cancel[0], cancel[1] - 0.073, cancel[2], cancel[3], "OK")
    if not ok:
        cancel_nickname()
        raise Stop(f"no OK on the nickname box: {summary()}")
    if DRY:
        log(f"  DRY RUN: the box reads {got!r}: would rename {old!r} -> {new!r}, CANCEL instead")
        cancel_nickname()
        wait("friend", timeout=8)
        return False
    tap_text(ok)
    wait("friend", timeout=8)
    log(f"  nickname {old!r} -> {new!r}")
    return True


def grey_check(t):
    """tap a grey SEND GIFT anyway. -> "picker" (the gift list opened: the grey read was wrong, now closed again),
    "empty" (the game says I have no gifts) or None (nothing opened: that friend just can't take one now)"""
    tap_text(t, dy=-0.04)
    s = wait("picker", "friend", "unknown", timeout=4)
    if s != "picker":
        time.sleep(1.0)
        s = look()
    if s == "picker":
        close()
        wait("friend", timeout=6)
        return "picker"
    j = joined()
    log(f"  tapped the grey SEND GIFT: {s}: {summary()}")
    keep_capture("grey_tap")
    if s != "friend":
        close()
        wait("friend", timeout=6)
    if "NO GIFT" in j or "DON'T HAVE" in j or "DO NOT HAVE" in j:
        return "empty"
    return None


def one_friend(row, check=False, done=None):
    """open the row's friend page, check, gift and/or tag. -> the gift sent, None (no gift, on purpose), "grey",
    "misread" (a friend already dealt with opened), "empty" or "raid".
    check: on a grey SEND GIFT, tap it anyway to see whether my bag is empty. done: name_keys dealt with this run.
    A page that isn't the row's name but no one done yet is a friend from the same list (OCR garbles some rows'
    names each look, 2026-11-07: '1234Lo', '1234) Jading'): it goes on with them"""
    t0 = time.time()
    s = tap_into(row["t"], "friend", "giftpopup", "luckytrade", "raid")
    if s == "raid":
        keep_capture("raid")
        log(f"  tapping {row['name']!r} opened a raid: left it")
        return "raid"  # (run_searches' to_list() closes it, and tries this friend once more)
    if s in ("giftpopup", "luckytrade"):
        close_popup("friend")  # their gift to me: X, never OPEN. A Lucky Trade request: X, left for the user
    name = page_name()
    if not name:
        # the page can count as open before its name loads (iPhone, 2026-11-07: 5 friends skipped as 'opened None')
        w0 = time.time()
        if poll_until(page_name, NAME_WAIT):
            log(f"  the name showed after {time.time() - w0:.1f}s")
        name = page_name()
    if name and not same_name(name, row["name"]) and done is not None and name_key(name) not in done:
        log(f"  opened {name!r}, the list read {row['name']!r}: going on with them")
        row = dict(row, name=name, nick="")  # (the list's nickname is unknown: a rename is left to the user)
    elif not name or not same_name(name, row["name"]):
        if not name:
            keep_capture("noname")
        log(f"  opened {name!r}, wanted {row['name']!r}: skipped")
        return "misread"
    if done is not None:
        done.add(name_key(name))
    nick, _ = page_nickname()
    if re.match(r"WAIT", nick):
        log(f"{name} ({nick}): tagged WAIT, skipped")  # (the list's WAIT check, for a page opened by a garbled row)
        return None
    if never_gift(name, nick):
        log(f"{name} ({nick}): never gets a gift from the script: left alone")
        return None
    t = send_gift_label()
    if not t or not gift_icon(t):
        # (or a Lucky Trade request fading in over the page: it pales the icon)
        # The list showed no sent badge, so they can take one: the icon is grey only till the game has asked the
        # server (iPhone, 2026-11-07). Look again every POLL till it colours, up to ICON_WAIT
        wait_s, w0 = 0.8 if WALK or row["badged"] else ICON_WAIT, time.time()
        poll_until(lambda: classify() == "luckytrade" or ((u := send_gift_label()) and gift_icon(u)), wait_s)
        if (u := send_gift_label()) and gift_icon(u):
            log(f"  SEND GIFT coloured after {time.time() - w0:.1f}s")
        if classify() == "luckytrade":
            close_popup("friend")
        t = send_gift_label()
    if not t or not gift_icon(t):
        if WALK:  # (a speed test: the friendship screen as for a gift, then back. Never the gift list)
            n = meter()
            log(f"{name} ({nick}): walked, {n if n is not None else '-'} points ({time.time() - t0:.1f}s)")
            return "walked"
        keep_capture("grey")
        got = grey_check(t) if t and check else None
        if got == "empty":
            return "empty"
        if got != "picker":
            log(f"{name} ({nick}): their SEND GIFT is grey: skipped")
            return "grey"
        log(f"{name} ({nick}): SEND GIFT read grey, but the gift list opened: going on")
    n = meter()
    if n == 1:
        if is_tagged("WAIT", nick):
            log(f"{name} ({nick}): 1 point to level up: no gift, already tagged WAIT")
            return None
        log(f"{name} ({nick}): 1 point to level up: no gift, tagging WAIT")
        rename("WAIT", nick, row["nick"])
        return None
    title = send_gift()
    log(f"{name} ({nick}): {'would send' if DRY else 'sent'} {title} ({time.time() - t0:.0f}s)")
    if n == 2:
        try:
            rename("SENT", nick, row["nick"])
        except base.Lost as e:  # (the gift went: count it, run_searches' to_list() takes it from wherever this is)
            keep_capture("lost_rename")
            log(f"  lost while tagging SENT ({e}): tag it by hand")
    return title


# ---------- a run ----------

def whose():
    """from the friend list: our trainer name on the ME tab -> trainer, and which gifts this account sends (San Francisco
    only when it can't be read)"""
    global whole_state, trainer
    import home
    me = None
    t = label("ME", 0.0, 0.12)
    if t:
        if tap_into(t, "profile", timeout=6 * LAG) == "profile":
            # the name can show a moment after the tab (2026-10-27: one look 0.7 s in read none, so a HashTagAJay
            # run went San Francisco only). OCR mixes up I, l, 1 and |: home.squash, as home.trainer() reads it
            for _ in range(int(4 * LAG)):
                time.sleep(0.5)
                look()
                top = home.squash(" ".join(u[4] for u in texts if u[1] < 0.4))
                me = next((k for k in home.TRAINERS if home.squash(k) in top), None)
                if me:
                    break
                clipped = home.clipped_names(texts, 0.4)  # (2026-11-10 iPhone: 'HashTagAJa' all ten looks)
                if len(clipped) == 1:
                    me = clipped[0]
                    break
            else:
                keep_capture("whose")
                log(f"  can't read the trainer name on the ME tab: {[u[4] for u in texts if u[1] < 0.4]}")
        to_list()
    trainer = me
    whole_state = me in CALIFORNIA
    log(f"account {me or 'unread'}: {'California' if whole_state else 'San Francisco'} gifts only")


def today():
    return time.strftime("%Y-%m-%d")


def iii_file():
    return os.path.expanduser(f"~/.config/pogo/gift_iii_{trainer}.json")  # (one per account: two phones never share one)


def iii_finished():
    """the "iii" zones this account has finished today"""
    if not trainer:
        return []
    try:
        with open(iii_file()) as f:
            d = json.load(f)
        return d["zones"] if d["day"] == today() else []
    except (OSError, ValueError, KeyError, TypeError):
        return []


def iii_remember(zone, day):
    """day: when this zone's search started. A search that ran past midnight proves nothing about the new day"""
    if DRY or not trainer or day != today():
        return
    os.makedirs(os.path.dirname(iii_file()), exist_ok=True)
    tmp = iii_file() + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"day": day, "zones": iii_finished() + [zone]}, f)
    os.replace(tmp, iii_file())
    log(f"  iii + {zone}: finished, skipped for the rest of {day}")


def run_searches(limit):
    sent, done, greys = 0, set(), 0
    lost, retried = 0, set()  # lost: one_friend's lost screens in a row; retried: friends already given a 2nd try
    to_list()
    whose()
    set_sort()
    for first, base_q in (("iii", FIRST), ("lll", THEN)):
        prev = None
        for zone, zq in ZONES:
            remembered = first == "iii" and zone != "rest"  # (rest: where a friend added today lands)
            if remembered and zone in iii_finished():
                log(f"iii + {zone}: finished earlier today: skipped")
                continue  # (prev stays: the box still holds that search)
            t0 = time.time()
            day = today()
            n = None
            if prev is not None and len(prev) == 2 and len(zq) <= 2:
                n = swap_zone(base_q, prev, zq)  # ea -> ce -> mo -> (none): change just the end
            if n is None:
                n = search(base_q, zq)
            prev = zq
            log(f"{first} + {zone}: ({n}) ({time.time() - t0:.0f}s)")
            if n == 0 and remembered:  # (a list slow to load can read 0: one false 0 would lose them all day)
                n = search(base_q, zq)
                if n == 0:
                    iii_remember(zone, day)
                else:
                    log(f"  searched again: ({n})")
            if not n:
                continue
            if arrow() != "down":
                set_sort()
            stale, fresh = 0, True  # fresh: the last capture is the friend list as it is now (no look needed)
            top = True  # the list is as a search sorted it: no gift sent since (scrolled or not)
            bounced = 0  # scrolls that landed off the list since the last friend reached
            finished, missed, seen = False, False, set()  # missed: a friend here wasn't dealt with; seen: names on the list
            tapped = []  # where rows were tapped since the list last moved: done, whatever OCR reads there next
            pinned = set()  # rows skipped for their spot alone (logged once)
            while True:
                if not fresh and look() != "friends":  # a drag that landed as a tap opened something: back first
                    bounced += 1
                    if bounced >= MAX_BOUNCED:
                        raise Stop(f"{bounced} scrolls in a row left the friend list: {summary()}")
                    to_list()
                fresh = False
                if search_gone():
                    # with no search on, a scrolled list has no '(N)' and reads as the profile: every scroll would
                    # come back to the top of the same page, forever (2026-11-03). Type it again
                    log("  the search is gone: searching again")
                    n = search(base_q, zq)
                    if not n:
                        break
                    if arrow() != "down":
                        set_sort()
                    stale, fresh, top, tapped = 0, True, True, []
                    continue
                on_screen = rows()
                seen |= {r["name"] for r in on_screen}
                # a Remote Trade friend stays at the top whatever the sort: their arrow says nothing about the rest
                # (never_gift here too: OCR can read a name differently each look, so done alone could reopen them)
                todo = [r for r in on_screen if name_key(r["name"]) not in done and not (r["trade"] and r["badged"])
                        and not never_gift(r["name"], r["nick"])]
                spot = [r for r in todo if any(abs(r["t"][1] - y) < 0.012 for y in tapped)]
                for r in spot:  # (a row already tapped, its name read another way: not opened again, but not proven done)
                    if r["name"] not in pinned:
                        pinned.add(r["name"])
                        log(f"  {r['name']!r} sits where a friend was tapped: skipped as done")
                missed = missed or bool(spot)
                todo = [r for r in todo if r not in spot]
                if todo and todo[0]["badged"] and not WALK:
                    if top:
                        finished = True
                        break  # sorted can-receive first, and the first friend not done has the arrow: nobody left
                    # the list re-sorts only on a new search: the friends gifted this run keep their place, arrow
                    # and all. Search again, then look at the top
                    log(f"  {todo[0]['name']} has the arrow: searching again to re-sort")
                    n = search(base_q, zq)
                    if not n:
                        break
                    if arrow() != "down":
                        set_sort()
                    stale, fresh, top, tapped = 0, True, True, []
                    continue
                if not todo:
                    before = [r["name"] for r in rows()]
                    # (a scroll leaves top alone: the sort holds below too. 2026-10-31: friends gifted this run sat
                    # unarrowed at the top after the new search, so every re-search scrolled past them to the same
                    # arrow, and searched again, forever)
                    drag(0.75, 0.4, settle=(0.35, 0.45))  # (a slow drag barely glides on: the list holds still soon)
                    tapped = []
                    look()
                    stale = stale + 1 if [r["name"] for r in rows()] == before else 0
                    if stale:
                        finished = len(seen) >= n  # (a drag that didn't move the list looks like the bottom too)
                        break  # the bottom of the list
                    fresh = classify() == "friends"
                    continue
                row = todo[0]
                bounced = 0
                done.add(name_key(row["name"]))  # (I and l, O and 0 alike: OCR reads them either way)
                tapped.append(row["t"][1])
                if re.match(r"WAIT", row["nick"].strip()):
                    log(f"  {row['name']} ({row['nick']}): tagged WAIT, skipped")  # (1 point to level up: no gift)
                    fresh = True
                    continue
                # a grey SEND GIFT alone proves nothing (that friend may not take one now). Every 3rd grey in a row,
                # tap it anyway: the gift list opening, or send_gift's OutOfGifts, tells whether the bag is empty
                try:
                    got = one_friend(row, check=greys % 3 == 2, done=done)
                except base.Lost as e:
                    # a late iPhone tap (two X's landing at once closed the friend page, 2026-10-28) left a screen
                    # nobody expected. Nothing was sent unseen: after SEND a lost screen is a Stop (but a Pixel game that
                    # took neither SEND tap gets restarted, send_gift). Back to the list, the search typed again (the way
                    # back can pass the map), and this friend tried once more
                    lost += 1
                    missed = True
                    if lost >= MAX_LOST:
                        raise Stop(f"lost {lost} times in a row: {e}") from e
                    keep_capture("lost_friend")
                    log(f"  lost on {row['name']!r} ({e}): back to the list")
                    time.sleep(2 * LAG)  # (a tap still on its way lands before the next look)
                    to_list()
                    if row["name"] not in retried:
                        retried.add(row["name"])
                        done.discard(name_key(row["name"]))  # (gifted after all: their SEND GIFT reads grey next time)
                    n = search(base_q, zq)
                    if not n:
                        break
                    if arrow() != "down":
                        set_sort()
                    stale, fresh, top, tapped = 0, True, True, []
                    continue
                lost = 0
                missed = missed or got in ("grey", "misread", "raid")  # (a grey one can take a gift minutes later)
                if got == "misread":
                    got = None
                if got == "raid":  # (a raid invite popped up under the tap: not this friend's fault)
                    if row["name"] not in retried:
                        retried.add(row["name"])
                        done.discard(name_key(row["name"]))
                        tapped.pop()  # (its spot too: the second try taps it again)
                    got = None
                if got == "empty":
                    log(f"the game says I have no gifts: out of gifts, done ({sent} sent)")
                    return sent, "out of gifts"
                greys = greys + 1 if got == "grey" else 0
                if greys >= 9:
                    log(f"9 grey SEND GIFTs in a row: likely out of gifts, done ({sent} sent)")
                    return sent, "likely out of gifts (9 grey SEND GIFTs in a row)"
                if got and got != "grey":
                    sent += 1
                    top = False  # their arrow now shows, but they keep their place until the next search
                    if sent >= limit:
                        log(f"{sent} gifts: the limit for this run")
                        return sent, None
                to_list()
                # the next friend is already known (rows keep their place until a new search): tap it the moment
                # the list shows. Only its rows may lag a moment behind the header
                if not rows():
                    poll_until(lambda: classify() != "friends" or rows(), 2.0)
                fresh = classify() == "friends"
            if remembered and finished and not missed:
                iii_remember(zone, day)
    return sent, "nobody left who can take one"


def one_phone(a):
    ui.CAP = f"/tmp/gift_{PHONE}.png"
    base.new_run_dir(os.path.join(HERE, "runs"), suffix=PHONE)
    global DRY, WALK
    DRY, WALK = a.dry_run, a.walk
    if a.cmd == "look":
        s = look()
        print(f"{PHONE}: {s}  rows: {rows() if s == 'friends' else '-'}  arrow: {arrow()}  gift sort: {sorted_gift()}")
        print("   ", summary())
        if s == "friend":
            print("    hearts:", heart_fill())
        return
    session.main(script, a.limit)


def script(limit):
    import home
    session.ready()  # iPhone Mirroring up (or the Pixel unlocked) before the first look
    try:
        s = look()
    except ui.Refused:  # Android: another app in front
        s = "unknown"
    if s in ("unknown", "blank", "map"):  # (home.start reads a scrolled friend page, SET NICKNAME, as a rename box)
        s = home.start(storage=False)
    log(f"Pokémon GO up, on {s}")
    try:
        sent, why = run_searches(limit)
        log(f"done: {sent} gifts {'would be sent (dry run)' if DRY else 'sent'}" + (f", {why}" if why else ""))
    except OutOfGifts:
        log("done: out of gifts (none we may send left): stopping")
        if not ui.ANDROID:
            to_list()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=("run", "look"))
    ap.add_argument("--limit", type=int, default=1000, help="at most N gifts per phone this run")
    ap.add_argument("--dry-run", action="store_true", help="everything but SEND and the nickname's OK")
    ap.add_argument("--walk", action="store_true", help="speed test, with --dry-run: friends already gifted too; "
                    "opens each one's page and friendship screen as for a gift, never the gift list")
    a = ap.parse_args()
    if a.walk and not a.dry_run:
        ap.error("--walk needs --dry-run")
    if os.environ.get("POGO_PHONE", "").lower() != "both":  # ui read POGO_PHONE on import: android, else the iPhone
        return one_phone(a)
    ui.ensure_helper()  # built once here, so the two phones don't both compile it
    procs = []
    for phone in ("ios", "android"):
        env = dict(os.environ, POGO_PHONE=phone)
        cmd = [sys.executable, os.path.realpath(__file__), a.cmd, "--limit", str(a.limit)]
        cmd += ["--dry-run"] if a.dry_run else []
        cmd += ["--walk"] if a.walk else []
        procs.append(subprocess.Popen(cmd, env=env))
    codes = [p.wait() for p in procs]
    sys.exit(max(codes))


if __name__ == "__main__":
    main()
