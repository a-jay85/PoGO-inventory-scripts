#!/usr/bin/env python3
"""/gift: send San Francisco gifts to every friend who can take one, the most useful first.

  caffeinate -dimsu python3 gift.py [--limit N]                       the iPhone
  POGO_PHONE=android caffeinate -dimsu python3 gift.py [--limit N]    the Android phone
  POGO_PHONE=both caffeinate -dimsu python3 gift.py [--limit N]       both phones at once
  [POGO_PHONE=android] python3 gift.py look                           what the script reads now; taps nothing

HashTagAJay is on the iPhone (iPhone Mirroring, hands off the Mac mouse), CyrillJan on the Android phone (adb).
Each phone runs in its own process (ui.py keeps one phone's state in module globals).

Order: the "iii" search (no gift from me, not played with today) before "lll" (opened my gift or played with me
today). Inside each, the time zones farthest ahead first: lasia, leuro, latam, ea, ce, mo, then the rest. The list
is sorted "Can receive a gift", arrow down: friends who can take a gift come first, so the first row with the grey
already-sent badge ends that search.

Before each gift the friendship screen is checked. When the next heart is the 3rd, 4th or 5th, or it's the Forever
Friends bar: 1 point to go -> no gift, nickname "WAIT <old>"; 2 points -> gift, nickname "SENT <old>".
Only gifts from San Francisco are sent (the city line under the title), never one with "lion", "tree" or "rock" in
its title, and never with a sticker. When a phone has none
left it stops; the other phone carries on. At the end the iPhone quits iPhone Mirroring and the Pixel locks.
Log and captures go in runs/<time>-<phone>/.
"""
import argparse, difflib, os, random, re, subprocess, sys, time
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, keep_capture
import session

CITY = "SAN FRANCISCO"  # the only gifts sent: the rest (Chicago, North Carolina ...) are kept for sending by hand
KEEP = re.compile(r"\b(lion|tree|(?<!mission )rock)", re.I)  # San Francisco gifts that are kept anyway (Lions, Trees, Rocky too; Mission Rock is sent)
# the user's text replacements on the iPhone ("iii", "lll", "lasia" ...): the iPhone types the shortcut and lets
# iOS expand it, Android types them out in full
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
SHORT = {FIRST: "iii", THEN: "lll", ZONES[0][1]: "lasia", ZONES[1][1]: "leuro", ZONES[2][1]: "latam"}
NICK_MAX = 12  # the game keeps the first 12 characters of a friend nickname
TYPEABLE = re.compile(r"[A-Za-z0-9 .,&!#+/*^=?$:;-]*")  # what the helper's keyboard (and adb) can type
X_BUTTON = (0.5, 0.937)  # the round X at the bottom middle (friend page, friendship screen, picker, gift preview)
SORT_BUTTON = (0.85, 0.935)
CLEAR_SEARCH = (0.86, 0.22)
HEART_Y = 0.384 if ui.ANDROID else 0.397  # the five big hearts on the friendship screen
HEART_X = (0.222, 0.362, 0.50, 0.64, 0.778) if ui.ANDROID else (0.234, 0.369, 0.505, 0.635, 0.768)
LEVELS = {"GOOD": 1, "GREAT": 2, "ULTRA": 3, "BEST": 4, "FOREVER": 5}  # ribbon -> hearts filled
WATCH_FROM = 2  # hearts index (0-based) from which a level-up is watched: the 3rd, 4th and 5th heart
HEART_NEAR = {2: 0.9, 3: 0.97, 4: 0.97, 5: 0.95}  # by hearts full: open the friendship screen only when the next one is this full.
# 3rd heart (~30 points): 1 to go read 100%, 2 read 94%, 5-6 read 81%. 4th/5th (~90-100 points, ~5 a pixel): 9 read 94%,
# 11 read 88%, 26 read 75%, 5 read 100%. The Forever bar (5, ~90 points over ~47 pixels): 60 read 36%
PHONE = "android" if ui.ANDROID else "ios"
DRY = False  # --dry-run: everything but SEND and the nickname box's OK
shortcuts = not ui.ANDROID  # off for the rest of the run once a shortcut didn't expand
typed = ""  # the last search typed: the box shows its end ('ea', 'mo')
LAG = 1 if ui.ANDROID else 2.5  # iPhone Mirroring now and then freezes for several seconds: wait longer there


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


def summary():
    return ui.summary(texts)


def classify():
    j, w = joined(), words()
    if "WHICH GIFT" in j:
        return "picker"
    if "ADD STICKER" in j and "SEND" in w:
        return "preview"
    if "GREETINGS FROM" in j and "OPEN" in w:
        return "giftpopup"
    if "REVIEW LUCKY" in j:
        return "luckytrade"  # a friend's Lucky Trade request over their page: its X shows the page
    if "TOTAL DAYS SPENT TOGETHER" in j:
        return "buddy"  # the buddy's history page (a stray tap on the ME tab's buddy): its X goes back
    if "TRAINER CODE" in j and "2D CODE" in j:
        return "trainercode"  # (a tap on our own picture in the friend list)
    if "SET NICKNAME" in j and w & {"OK", "CANCEL"}:
        return "nickname"
    # the gift list scrolled past its header: two columns of city lines ('Chicago, IL, United States')
    # (letters: the profile's ME tab has two columns of numbers like '145,619,768')
    cities = [t for t in texts if t[1] > 0.12 and t[4].count(",") >= 1 and len(t[4]) > 8
              and re.search(r"[^\W\d_]{3}", t[4])]
    if "SEND GIFT" not in j and {t[0] < 0.4 for t in cities} == {True, False} and len(cities) >= 3:
        return "picker"
    if "CAN RECEIVE A GIFT" in j and "FRIENDSHIP LEVEL" in j:
        return "sortmenu"
    if "SEND GIFT" in j:
        return "friend"
    if "BONUS" in w or "MORE FRIENDSHIP POINT" in j or ribbon():
        return "meter"
    if "EXIT POK" in j:
        return "exit"
    if "FRIENDS" in w and ("ME" in w or "SOCIAL" in w):
        if "TOTAL ACTIVITY" in j or w & {"SCRAPBOOK", "JOURNAL"}:
            return "profile"  # the ME tab: its trainer name sits where the search box would be
        if w & {"ADD FRIEND", "INVITE", "TRAINER NICKNAME"} or search_line() or count() is not None:
            return "friends"
        return "profile"
    from search import pokeball
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
    Between looks: 0.4 s on the iPhone, none on Android"""
    return base.wait_for(*screens, timeout=timeout, look=lambda: (look(), texts, path, bounds),
                         poll=base.poll_gap(0.4), catch=False, capture=False, detail=True)[0]


def tap(fx, fy, fuzz=0.008, rest=None):
    """rest: seconds to wait after the tap (default a short random pause)"""
    base.click(fx, fy, bounds, fuzz=fuzz, rest=(0.25, 0.4) if rest is None else rest)


def tap_text(t, dy=0.0, rest=None):
    base.tap_box(t, bounds, dy=dy, fuzz=min(0.008, t[2] / 4), rest=(0.25, 0.4) if rest is None else rest)


def drag(fy1, fy2, ms=500, x=None):
    """scroll by dragging from fy1 to fy2. x: where to grab (the gift list: the gap between its two columns, as a
    drag that starts on a card can land as a tap on it)"""
    x = x if x is not None else random.uniform(0.4, 0.6)
    base.drag(x, fy1, x + random.uniform(-0.005, 0.005), fy2, bounds, ms=ms, settle=(0.7, 1.0),
              android_settle=base.LIST_SETTLE)


def close():
    tap(*X_BUTTON, fuzz=0.004)  # (the preview's SEND sits just above: keep the X tap tight)
    time.sleep(1.0)


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


def to_list():
    unknown, acted, end = 0, (None, 0.0), time.time() + 90
    while time.time() < end:
        s = look()
        if s == "friends":
            return
        if s == acted[0] and s != "unknown" and time.time() - acted[1] < 3 * LAG:
            time.sleep(0.3)  # the last tap hasn't shown yet: look again, don't tap twice
            continue
        unknown = unknown + 1 if s == "unknown" else 0
        acted = (s, time.time())
        if s == "profile":
            t = label("FRIENDS")
            tap_text(t) if t else tap(0.5, 0.09)
        elif s == "map":
            tap(0.13, 0.91)  # the profile picture
        elif s in ("friend", "meter", "picker", "preview", "giftpopup", "luckytrade", "trainercode", "buddy"):
            close()
        elif s == "nickname":
            cancel_nickname()
        elif s == "sortmenu":
            tap_text(label("CAN RECEIVE A GIFT"))  # set_sort() checks the arrow after
        elif s == "exit":
            tap_text(label("CANCEL"))
        elif s == "unknown" and ui.classify(texts) in ("list", "tag-tab", "detail"):
            close()  # Pokémon storage: its X goes back to the map
        elif s == "unknown" and unknown > 2:
            keep_capture("lost")
            import home
            home.unstick(texts)
            unknown = 0
        time.sleep(0.5)
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
        tap_text(label("CAN RECEIVE A GIFT"))
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


def to_top():
    global typed
    before = None
    for _ in range(15):
        if look() != "friends":
            to_list()  # (a drag can land as a tap and open a friend's gift)
        if search_line() or label("SEARCH", 0.18, 0.28):
            return
        rows_now = [r["name"] for r in rows()]
        box = [t for t in texts if 0.18 < t[1] < 0.26 and t[0] < 0.25 and len(t[4].strip()) >= 2]
        if rows_now == before and count() is not None and box:
            typed = box[0][4].strip()  # a scroll up moved nothing: the top, so this is the box (an older search's end, 'ea')
            return
        before = rows_now
        drag(0.35, 0.8, 350)
    raise Stop(f"couldn't scroll back to the search box: {summary()}")


def type_query(parts):
    """iPhone: a part with a text replacement goes in as its shortcut and a space (iOS expands it on the space),
    then the space comes off"""
    for p in parts:
        if shortcuts and p in SHORT:
            base.type_text(SHORT[p] + " ")
            time.sleep(0.3)
            base.key("delete")
        elif p:
            base.type_text(p)


def expanded(parts):
    """after a search with shortcuts: False only when the box still shows a shortcut ('iiilasia'). The box shows
    just the end of a long search, so a short read ('mo') or no read at all says nothing"""
    box = search_line()
    t = ui.norm(box[4]).replace(" ", "") if box else ""
    return not any(SHORT[p].upper() in t for p in parts if p in SHORT)


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


def search(*parts):
    """type a search (its parts, joined) into the friend list -> its result count"""
    global shortcuts, typed
    q = "".join(parts)
    for attempt in range(4):
        to_top()
        if search_line() and ui.norm(search_line()[4]) != "TRAINER NICKNAME":
            tap(*CLEAR_SEARCH, fuzz=0.004)
            time.sleep(1.0)
            look()
        s = label("SEARCH", 0.18, 0.28)
        if s:
            tap_text(s, dy=-0.035)
        else:
            tap(0.45, 0.22)  # an empty box ("Trainer Nickname")
        time.sleep(1.2)
        short = shortcuts
        typed = q
        type_query(parts)
        n = commit_search()
        if n is None:
            keep_capture("nocount")
            log(f"no result count after the search (the box reads {search_line()[4] if search_line() else None!r}): typing it again")
            continue
        box = search_line()
        log(f"  search box reads {box[4] if box else None!r}")
        if short and any(p in SHORT for p in parts) and not expanded(parts):
            shortcuts = False
            log("the text shortcuts didn't expand: typing searches out in full from now on")
            continue
        if n == 0 or rows():
            return n
        n = add_space(n)
        if n is not None and (n == 0 or rows()):
            return n
        log(f"still ({n}) and no rows: typing it again")
    raise Stop(f"the search {q!r} didn't take after 4 tries: {summary()}")


def add_space(n):
    """a known game bug: a count with an empty list. A space added to the end runs the search again -> the count"""
    global typed
    log(f"the search shows ({n}) but no rows: adding a space")
    box = search_line()
    tap_text(box) if box else tap(0.45, 0.22)
    time.sleep(1.2)
    base.type_text(" ")
    typed += " "
    return commit_search()


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
    t = ui.norm(box[4]).replace(" ", "").rstrip("X") if box else ""  # (the read can end with the box's clear X)
    log(f"  search box reads {box[4] if box else None!r}")
    if n is None or (not t.endswith(new.upper()) if new else t.endswith(old.upper())):
        log(f"swapping {old!r} for {new!r} didn't take: typing the search again")
        return None
    if n and not rows():
        n = add_space(n)
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
                  and "SENT YOU" not in ui.up(t) and "TRADE REQUEST" not in ui.up(t)), key=lambda t: t[1])  # ('<name> sent you a Lucky Remote Trade request.')
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
    return [{"name": clean(t[4]), "nick": nick, "t": t, "badged": badged(im, t[1])} for t, nick in out if t[1] > 0.26]


def same_name(a, b):
    """the row's name and the page's: OCR reads them a little differently ('lycбo' / 'lyc60'). One letter off is ok"""
    f = lambda s: re.sub(r"[il1|Iİı]", "l", re.sub(r"[oO0]", "0", clean(s).replace("&", "8"))).lower()
    a, b = f(a), f(b)
    return a == b or len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1


# ---------- one friend ----------

def page_name():
    top = [t for t in texts if 0.07 < t[1] < 0.16 and t[0] < 0.25 and '"' not in t[4]
           and re.fullmatch(r"[\w&]{3,}", clean(t[4]))]  # (below the status bar's clock; OCR reads an 8 as &: "Gr&estGuyEver")
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
    for t in texts:
        m = re.fullmatch(r"(GOOD|GREAT|ULTRA|BEST|FOREVER) FRIEND", ui.up(t))
        if m and 0.2 < t[1] < 0.36:
            return m.group(1)
    return None


def points_text():
    j = joined()
    m = re.search(r"EARN (\d+) MORE FRIENDSHIP POINT", j)
    return int(m.group(1)) if m else None


def forever_fill(im, W, H):
    """a Forever Friend's bar right of the small heart -> (5, how full, 0-1), or None. It fills orange from the left
    over grey; each step is about 90 points (60 to go read 34%, 80 read 13%)"""
    def kind(r, g, b):
        if r > 220 and 90 < g < 200 and b < 120:
            return "O"
        if abs(r - g) < 14 and abs(g - b) < 14 and 140 < r < 230:
            return "g"
        return "."

    best = None
    for cy in range(int(H * 0.15), int(H * 0.23)):
        line = "".join(kind(*im.getpixel((x, cy))) for x in range(int(W * 0.08), int(W * 0.35)))
        for run in re.split(r"\.{2,}", line):  # (one stray pixel inside the bar is fine)
            if len(run) > 0.08 * W and (best is None or len(run) > len(best)):
                best = run
    if best is None:
        return None
    return 5, best.count("O") / (best.count("O") + best.count("g"))


def heart_fill():
    """the five small hearts under the name on the friend page -> (hearts full, how full the next one is, 0-1),
    or None when they can't be read (a Forever Friend's smaller heart + bar, a lucky friend's swirl).
    A full heart is red; the next one fills yellow from the left, the rest grey. The gaps between hearts are
    sometimes grey too, so each heart is cut out by its spot, measured from the first one's left edge"""
    im = Image.open(path).convert("RGB")
    W, H = im.size

    def kind(ps):
        if any(p[0] > 230 and p[1] < 140 and p[2] < p[0] - 60 for p in ps):
            return "R"
        if any(p[0] > 230 and 140 <= p[1] < 215 and p[2] < p[0] - 60 for p in ps):
            return "Y"
        return "."

    best = ""
    for cy in range(int(H * 0.15), int(H * 0.23)):  # (a nickname above is orange-yellow text: count red only)
        line = "".join(kind([im.getpixel((x, y)) for y in range(cy - 2, cy + 3)]) for x in range(int(W * 0.04), int(W * 0.32)))
        if line.count("R") > best.count("R"):
            best = line
    if "R" not in best:
        return None
    pitch = (0.0456 if ui.ANDROID else 0.0437) * W  # 18.5 / 17.7 px apart on a 406 px wide capture
    a, width = best.index("R"), round(0.0394 * W)  # 16 px hearts
    if len(best[a:]) - len(best[a:].lstrip("R")) < 0.8 * width:
        return forever_fill(im, W, H)  # a Forever Friend: a smaller heart, then the bar
    fill = []
    for i in range(5):
        seg = best[a + round(i * pitch):][:width]
        fill.append((seg.count("R") >= 0.7 * width, (seg.count("R") + seg.count("Y")) / width))
    full = next((i for i, (red, _) in enumerate(fill) if not red), 5)
    return full, (fill[full][1] if full < 5 else 1.0)


def meter():
    """-> friendship points to the next level when that level is the 3rd, 4th or 5th heart or the Forever bar,
    else None (a level-up there doesn't matter). Leaves the friend page showing again"""
    hf = heart_fill()
    if hf and (hf[0] < WATCH_FROM or hf[1] < HEART_NEAR[hf[0]]):  # (5 full hearts read 100%: always opened)
        log(f"  {hf[0]} hearts + {hf[1]:.0%} of the next: no level-up close, friendship screen not opened")
        return None
    nick, line = page_nickname()
    spots = [(0.12, line[1] + line[3] / 2)] if line else []
    spots += [(0.15, 0.177), (0.15, 0.204)]
    for fx, fy in spots:
        tap(fx, fy, fuzz=0.004)
        try:
            wait("meter", timeout=4)
            break
        except Stop:
            if look() != "friend":
                close()
    else:
        keep_capture("meter")
        raise Stop(f"the friendship screen didn't open: {summary()}")
    if not ribbon():  # (still sliding in: wait() caught it early)
        time.sleep(0.8)
        look()
    level = ribbon()
    n = points_text()  # the Forever Friends bar shows its points with no tap
    if n is None and level != "GOOD":
        start = LEVELS[level] if level in LEVELS and LEVELS[level] >= WATCH_FROM else WATCH_FROM
        for i in range(start, 5):
            tap(HEART_X[i], HEART_Y, fuzz=0.004)
            time.sleep(0.9)
            look()
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
    block, y = [t], t[1]
    for u in col:
        if 0 < u[1] - y < 0.035:
            block.append(u)
            y = u[1]
    for i, u in enumerate(block[1:4], 1):
        if "," in u[4]:
            return " ".join(v[4].strip() for v in block[:i]), u[4].strip()
    return None, None


def ours(title, city):
    return bool(title) and "," not in title and city.upper().startswith(CITY) and not KEEP.search(title)


def card_title(t):
    """the gift's title, if t starts the title of one we may send"""
    title, city = title_block(t, texts)
    return title if ours(title, city or "") else None


def preview_ok(title):
    """the preview reads 'Greetings from' / the title / the city"""
    lines = sorted(texts, key=lambda t: t[1])
    for i, t in enumerate(lines):
        if "GREETINGS FROM" in ui.up(t):
            # (only 'Greetings from''s column: words printed on the postcard photo sit to its left, 'JACK LONDON')
            rest = [u for u in lines[i + 1:] if u[1] - t[1] < 0.15 and abs(u[0] - t[0]) < 0.03]
            got, city = title_block(rest[0], rest, left=True) if rest else (None, None)
            cut = title.rstrip(".… ")  # the picker cuts a long title short ('Modern spiral chandeli')
            near = lambda a, b: difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.9  # (a letter misread: 'Lot Al')
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


def send_gift():
    """from the friend page: picker -> one of our two gifts -> SEND. Raises OutOfGifts when neither is there"""
    global picker_drags
    t = label("SEND GIFT")
    tap_text(t, dy=-0.04)
    wait("picker", timeout=8)
    blind = max(0, picker_drags - 1)  # where the last gift was found, less one scroll (a sent gift can shift the list up)
    drags = 0
    seen, dragged = None, None  # seen: the last look's layout; dragged: the layout and titles when it last scrolled
    for i in range(200):  # (about 3 looks a scroll: the first look after one still catches the list moving)
        if drags >= 60:  # (a full bag is a long list: 12 scrolls weren't enough on 2026-10-26)
            break
        if i:  # (the first pass reads the capture wait() just took)
            time.sleep(0.6)
            look()
        cards = [(card_title(t), t) for t in texts if t[1] > 0.2]
        cards = [(n, t) for n, t in cards if n and t[1] - 0.11 > 0.18]
        if cards:
            picker_drags = drags
            title, t = cards[0]
            tap(t[0] + t[2] / 2, t[1] - 0.11)  # the postcard above its title
            wait("preview", timeout=6 * LAG)
            ok, got = preview_ok(title)
            if not ok:  # (caught mid-animation: one more look)
                time.sleep(0.5)
                look()
                ok, got = preview_ok(title)
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
                raise Stop(f"no SEND on the preview: {summary()}")
            if DRY:
                log(f"  DRY RUN: would SEND {title}")
                close()
                wait("picker", timeout=6)
                close()
                wait("friend", timeout=6)
                return title
            button = send_button(send)
            tap_text(send, rest=0)
            if sent_away(send, button):  # SEND is gone and the gift flies off: an X right now skips the animation
                tap(*X_BUTTON, fuzz=0.004, rest=0)
            s = wait("friend", "picker", "preview", "unknown", "blank", timeout=8 * LAG)
            for _ in range(int(10 * LAG)):
                if s == "friend":
                    return title
                time.sleep(0.6)
                s = look()
            keep_capture("after_send")
            raise Stop(f"after SEND the screen is {s}: {summary()}")
        if classify() != "picker":
            keep_capture("not_picker")
            raise Stop(f"left the gift list while looking for our gifts: {summary()}")
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
                drag(0.75, 0.45, x=0.5 + random.uniform(-0.005, 0.005))
            drags = blind - 1
            dragged = None  # (these scrolls weren't checked: the next one mustn't read as the list's end)
        drag(0.75, 0.45, x=0.5 + random.uniform(-0.005, 0.005))
        drags += 1
    raise Stop(f"scrolled the gift list {drags} times without reaching its end")


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


def one_friend(row, check=False):
    """open the row's friend page, check, gift and/or tag. -> the gift sent, None, "grey" or "empty".
    check: on a grey SEND GIFT, tap it anyway to see whether my bag is empty"""
    t0 = time.time()
    tap_text(row["t"])
    s = wait("friend", "giftpopup", "luckytrade", timeout=8)
    if s in ("giftpopup", "luckytrade"):
        close()  # their gift to me: X, never OPEN. A Lucky Trade request: X, left for the user
        wait("friend", timeout=6)
    name = page_name()
    if not name or not same_name(name, row["name"]):
        log(f"  opened {name!r}, wanted {row['name']!r}: skipped")
        return None
    nick, _ = page_nickname()
    t = label("SEND GIFT")
    if not gift_icon(t):
        time.sleep(0.8)  # (or a Lucky Trade request fading in over the page: it pales the icon)
        if look() == "luckytrade":
            close()
            wait("friend", timeout=6)
        t = label("SEND GIFT")
    if not t or not gift_icon(t):
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
        log(f"{name} ({nick}): 1 point to level up: no gift, tagging WAIT")
        rename("WAIT", nick, row["nick"])
        return None
    title = send_gift()
    log(f"{name} ({nick}): {'would send' if DRY else 'sent'} {title} ({time.time() - t0:.0f}s)")
    if n == 2:
        rename("SENT", nick, row["nick"])
    return title


# ---------- a run ----------

def run_searches(limit):
    sent, done, greys = 0, set(), 0
    to_list()
    set_sort()
    for first, base_q in (("iii", FIRST), ("lll", THEN)):
        prev = None
        for zone, zq in ZONES:
            t0 = time.time()
            n = None
            if prev is not None and len(prev) == 2 and len(zq) <= 2:
                n = swap_zone(base_q, prev, zq)  # ea -> ce -> mo -> (none): change just the end
            if n is None:
                n = search(base_q, zq)
            prev = zq
            log(f"{first} + {zone}: ({n}) ({time.time() - t0:.0f}s)")
            if not n:
                continue
            if arrow() != "down":
                set_sort()
            stale, fresh = 0, True  # fresh: the last capture is the friend list as it is now (no look needed)
            top = True  # the list is at its top, just sorted by a search: nothing scrolled, no gift sent since
            while True:
                if not fresh and look() != "friends":  # a drag that landed as a tap opened something: back first
                    to_list()
                fresh = False
                on_screen = rows()
                todo = [r for r in on_screen if r["name"] not in done]
                if todo and todo[0]["badged"]:
                    if top:
                        break  # sorted can-receive first, and the first friend not skipped has the arrow: nobody left
                    # the list re-sorts only on a new search: the friends gifted this run keep their place, arrow
                    # and all. Search again, then look at the top
                    log(f"  {todo[0]['name']} has the arrow: searching again to re-sort")
                    n = search(base_q, zq)
                    if not n:
                        break
                    if arrow() != "down":
                        set_sort()
                    stale, fresh, top = 0, True, True
                    continue
                if not todo:
                    before = [r["name"] for r in rows()]
                    drag(0.75, 0.4)
                    top = False
                    look()
                    stale = stale + 1 if [r["name"] for r in rows()] == before else 0
                    if stale:
                        break  # the bottom of the list
                    fresh = classify() == "friends"
                    continue
                row = todo[0]
                done.add(row["name"])
                # a grey SEND GIFT alone proves nothing (that friend may not take one now). Every 3rd grey in a row,
                # tap it anyway: the gift list opening, or send_gift's OutOfGifts, tells whether the bag is empty
                got = one_friend(row, check=greys % 3 == 2)
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
                fresh = True
    return sent, "nobody left who can take one"


def one_phone(a):
    ui.CAP = f"/tmp/gift_{PHONE}.png"
    base.new_run_dir(os.path.join(HERE, "runs"), suffix=PHONE)
    global DRY
    DRY = a.dry_run
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
        log(f"done: {sent} gifts sent" + (f", {why}" if why else ""))
    except OutOfGifts:
        log("done: out of gifts (none from San Francisco we may send left): stopping")
        if not ui.ANDROID:
            to_list()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=("run", "look"))
    ap.add_argument("--limit", type=int, default=1000, help="at most N gifts per phone this run")
    ap.add_argument("--dry-run", action="store_true", help="everything but SEND and the nickname's OK")
    a = ap.parse_args()
    if os.environ.get("POGO_PHONE", "").lower() != "both":  # ui read POGO_PHONE on import: android, else the iPhone
        return one_phone(a)
    ui.ensure_helper()  # built once here, so the two phones don't both compile it
    procs = []
    for phone in ("ios", "android"):
        env = dict(os.environ, POGO_PHONE=phone)
        cmd = [sys.executable, os.path.abspath(__file__), a.cmd, "--limit", str(a.limit)]
        cmd += ["--dry-run"] if a.dry_run else []
        procs.append(subprocess.Popen(cmd, env=env))
    codes = [p.wait() for p in procs]
    sys.exit(max(codes))


if __name__ == "__main__":
    main()
