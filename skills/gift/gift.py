#!/usr/bin/env python3
"""/gift: send Mission Walk / Mission Creek Park gifts to every friend who can take one, the most useful first.

  caffeinate -dimsu python3 gift.py [--limit N]                 both phones at once
  caffeinate -dimsu python3 gift.py --phone ios|android [--limit N]
  python3 gift.py --phone ios|android look                      what the script reads now; taps nothing

HashTagAJay is on the iPhone (iPhone Mirroring, hands off the Mac mouse), CyrillJan on the Android phone (adb).
Each phone runs in its own process (ui.py keeps one phone's state in module globals).

Order: the "iii" search (no gift from me, not played with today) before "lll" (opened my gift or played with me
today). Inside each, the time zones farthest ahead first: lasia, leuro, latam, ea, ce, mo, then the rest. The list
is sorted "Can receive a gift", arrow down: friends who can take a gift come first, so the first row with the grey
already-sent badge ends that search.

Before each gift the friendship screen is checked. When the next heart is the 3rd, 4th or 5th, or it's the Forever
Friends bar: 1 point to go -> no gift, nickname "WAIT <old>"; 2 points -> gift, nickname "SENT <old>".
Only gifts titled exactly "Mission Walk" or "Mission Creek Park" are sent, with no sticker. When a phone has none
left it stops (the iPhone quits iPhone Mirroring); the other phone carries on.
Log and captures go in runs/<time>-<phone>/.
"""
import argparse, os, random, re, subprocess, sys, time
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, keep_capture

GIFTS = ("Mission Walk", "Mission Creek Park")  # never any other: the rest are kept for sending by hand
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
HEART_NEAR = 0.75  # open the friendship screen only when the next small heart is this full (2 points to go reads ~91%, 11 read 56%)
PHONE = "android" if ui.ANDROID else "ios"
DRY = False  # --dry-run: everything but SEND and the nickname box's OK
shortcuts = not ui.ANDROID  # off for the rest of the run once a shortcut didn't expand
LAG = 1 if ui.ANDROID else 2.5  # iPhone Mirroring now and then freezes for several seconds: wait longer there


def log(msg):
    base.log(f"{PHONE:7} {msg}")  # the two phones print to the same terminal


class OutOfGifts(Exception):
    pass


# ---------- screen ----------

texts, path, bounds = [], None, None


def up(t):
    return t[4].upper().strip()


def words():
    return {ui.norm(t[4]) for t in texts}


def joined():
    return " ".join(up(t) for t in texts)


def find(pred):
    return [t for t in texts if pred(t)]


def label(name, lo=0.0, hi=1.0):
    hits = find(lambda t: ui.norm(t[4]) == name and lo <= t[1] <= hi)
    return hits[0] if hits else None


def summary():
    return " | ".join(t[4] for t in texts)[:250]


def classify():
    j, w = joined(), words()
    if "WHICH GIFT" in j:
        return "picker"
    if "ADD STICKER" in j and "SEND" in w:
        return "preview"
    if "GREETINGS FROM" in j and "OPEN" in w:
        return "giftpopup"
    if "SET NICKNAME" in j and w & {"OK", "CANCEL"}:
        return "nickname"
    # the gift list scrolled past its header: two columns of city lines ('Chicago, IL, United States')
    cities = [t for t in texts if t[1] > 0.12 and t[4].count(",") >= 1 and len(t[4]) > 8]
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
    global texts, path, bounds
    path, bounds = ui.capture()
    texts = ui.ocr(path)
    return classify()


def wait(*screens, timeout=10):
    end = time.time() + timeout
    while True:
        s = look()
        if s in screens:
            return s
        if time.time() > end:
            raise Stop(f"wanted {'/'.join(screens)}, screen is {s}: {summary()}")
        time.sleep(0.4)


def tap(fx, fy, fuzz=0.008):
    base.front()
    base.tap_gap()
    x, y = base.to_points(fx + random.uniform(-fuzz, fuzz), fy + random.uniform(-fuzz / 2, fuzz / 2), bounds)
    ui.sh(ui.HELPER, "click", f"{x:.1f}", f"{y:.1f}", str(ui.tap_ms()))
    base.last_tap = time.time()
    time.sleep(random.uniform(0.25, 0.4))


def tap_text(t, dy=0.0):
    x, y, w, h, _ = t
    tap(x + w / 2, y + h / 2 + dy, fuzz=min(0.008, w / 4))


def drag(fy1, fy2, ms=500, x=None):
    """scroll by dragging from fy1 to fy2. x: where to grab (the gift list: the gap between its two columns, as a
    drag that starts on a card can land as a tap on it)"""
    base.front()
    x = x if x is not None else random.uniform(0.4, 0.6)
    x1, y1 = base.to_points(x, fy1, bounds)
    x2, y2 = base.to_points(x + random.uniform(-0.005, 0.005), fy2, bounds)
    ui.sh(ui.HELPER, "drag", f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}", str(ms))
    time.sleep(random.uniform(0.7, 1.0))


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
    for t in texts:
        if 0.18 < t[1] < 0.26 and t[0] < 0.25 and ui.norm(t[4]) not in ("ADD FRIEND", "SEARCH", "INVITE", "OFFLINE"):
            return t
    return None


def to_list():
    unknown = 0
    for _ in range(30):
        s = look()
        unknown = unknown + 1 if s == "unknown" else 0
        if s == "friends":
            return
        if s == "profile":
            t = label("FRIENDS")
            tap_text(t) if t else tap(0.5, 0.09)
        elif s == "map":
            tap(0.13, 0.91)  # the profile picture
        elif s in ("friend", "meter", "picker", "preview", "giftpopup"):
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
        time.sleep(1.2)
    keep_capture("lost")
    raise Stop(f"couldn't get to the friend list: {summary()}")


def arrow():
    """'down' / 'up' / None: the small light arrow by the sort button. The gift icon has an arrow of its own:
    the direction arrow is the right-most one"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    light = {(x, y) for x in range(int(W * .86), int(W * .99)) for y in range(int(H * .89), int(H * .98))
             if im.getpixel((x, y))[0] >= 120 and min(im.getpixel((x, y))) <= 200}
    seen, found = set(), []
    for p in light:
        if p in seen:
            continue
        stack, blob = [p], []
        seen.add(p)
        while stack:
            x, y = stack.pop()
            blob.append((x, y))
            for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if q in light and q not in seen:
                    seen.add(q)
                    stack.append(q)
        xs, ys = [b[0] for b in blob], [b[1] for b in blob]
        w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        if 6 <= w <= 14 and 6 <= h <= 14 and len(blob) >= 15:
            found.append((min(xs), blob, min(ys), h))
    if not found:
        return None
    _, blob, top, h = max(found)
    head_up = sum(1 for x, y in blob if y < top + h / 3)
    head_down = sum(1 for x, y in blob if y >= top + 2 * h / 3)
    return "up" if head_up > head_down else "down" if head_down > head_up else None


def set_sort():
    """Can receive a gift, arrow down. Picking the sort that's already on flips its arrow: pick, read, again"""
    for attempt in range(4):
        tap(*SORT_BUTTON, fuzz=0.004)
        wait("sortmenu", timeout=6)
        tap_text(label("CAN RECEIVE A GIFT"))
        time.sleep(1.2)
        wait("friends", timeout=6)
        way = arrow()
        if way == "down":
            log("sorted Can receive a gift, arrow down")
            return
        log(f"sort arrow reads {way}: again")
    keep_capture("sort")
    raise Stop("couldn't get the list sorted Can receive a gift, arrow down")


def to_top():
    for _ in range(15):
        if search_line() or label("SEARCH", 0.18, 0.28):
            return
        drag(0.35, 0.8, 350)
        look()
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
    """after a search with shortcuts: False when the box still shows a shortcut ('iii lasia') or too little text"""
    box = search_line()
    t = ui.norm(box[4]).replace(" ", "") if box else ""
    return len(t) > 12 and not any(SHORT[p].upper() in t for p in parts if p in SHORT)


def search(*parts):
    """type a search (its parts, joined) into the friend list -> its result count"""
    global shortcuts
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
        type_query(parts)
        time.sleep(0.5)
        look()
        ok = find(lambda t: ui.norm(t[4]) == "OK" and t[0] > 0.75 and 0.5 < t[1] < 0.65)
        if ok:
            tap_text(ok[0])  # Android: the input strip's OK commits (Back would throw the text away)
        else:
            base.key("return")
        time.sleep(1.5)
        n = None
        for _ in range(8):
            if look() == "friends" and count() is not None:
                n = count()
                break
            time.sleep(0.5)
        if n is None:
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
        log(f"the search shows ({n}) but no rows: typing it again")  # Android, seen twice
    raise Stop(f"the search {q!r} didn't take after 4 tries: {summary()}")


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
    under it; rows too low to see their badge are left for the next scroll"""
    col = sorted((t for t in texts if 0.26 < t[0] < 0.32 and 0.26 < t[1] < 0.85 and t[4].strip()), key=lambda t: t[1])
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
    return [{"name": clean(t[4]), "nick": nick, "t": t, "badged": badged(im, t[1])} for t, nick in out]


def same_name(a, b):
    """the row's name and the page's: OCR reads them a little differently ('lycбo' / 'lyc60'). One letter off is ok"""
    f = lambda s: re.sub(r"[il1|I]", "l", re.sub(r"[oO0]", "0", clean(s))).lower()
    a, b = f(a), f(b)
    return a == b or len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1


# ---------- one friend ----------

def page_name():
    top = [t for t in texts if 0.07 < t[1] < 0.16 and t[0] < 0.25 and '"' not in t[4]
           and re.fullmatch(r"\w{3,}", clean(t[4]))]  # (below the status bar's clock)
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


def ribbon():
    for t in texts:
        m = re.fullmatch(r"(GOOD|GREAT|ULTRA|BEST|FOREVER) FRIEND", up(t))
        if m and 0.2 < t[1] < 0.36:
            return m.group(1)
    return None


def points_text():
    j = joined()
    m = re.search(r"EARN (\d+) MORE FRIENDSHIP POINT", j)
    return int(m.group(1)) if m else None


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
    a, pitch, width = best.index("R"), 0.0437 * W, round(0.0394 * W)  # iPhone: 16 px hearts, 17.7 px apart
    if len(best[a:]) - len(best[a:].lstrip("R")) < 0.8 * width:
        return None  # a Forever Friend: a smaller heart, then the bar
    fill = []
    for i in range(5):
        seg = best[a + round(i * pitch):][:width]
        fill.append((seg.count("R") >= 0.7 * width, (seg.count("R") + seg.count("Y")) / width))
    full = next((i for i, (red, _) in enumerate(fill) if not red), 5)
    return full, (fill[full][1] if full < 5 else 1.0)


def meter():
    """-> friendship points to the next level when that level is the 3rd, 4th or 5th heart or the Forever bar,
    else None (a level-up there doesn't matter). Leaves the friend page showing again"""
    hf = None if ui.ANDROID else heart_fill()  # (not checked on the Pixel's screenshots yet)
    if hf and (hf[0] < WATCH_FROM or (hf[0] < 5 and hf[1] < HEART_NEAR)):
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


def card_title(t):
    """the gift's exact title, if t is one of the two we may send. A long title wraps onto a second line: one
    that only starts with the name isn't ours. The line under a full title is the city ('San Francisco, ...')"""
    s = t[4].strip()
    below = [u for u in texts if 0 < u[1] - t[1] < 0.035 and abs(u[0] - t[0]) < 0.06]
    nxt = below[0][4].strip() if below else ""
    if s == "Mission Creek" and nxt == "Park":
        return "Mission Creek Park"
    if s in GIFTS and (not nxt or "," in nxt or nxt.upper().startswith("SAN FRANCISCO")):
        return s
    return None


def preview_ok(title):
    """the preview reads 'Greetings from' / the title / the city"""
    lines = sorted(texts, key=lambda t: t[1])
    for i, t in enumerate(lines):
        if "GREETINGS FROM" in up(t):
            rest = [u[4].strip() for u in lines[i + 1:i + 3]]
            got = rest[0] if rest else ""
            if got == "Mission Creek" and len(rest) > 1 and rest[1] == "Park":
                got = "Mission Creek Park"
            return got == title, got
    return False, None


def send_gift():
    """from the friend page: picker -> one of our two gifts -> SEND. Raises OutOfGifts when neither is there"""
    t = label("SEND GIFT")
    tap_text(t, dy=-0.04)
    wait("picker", timeout=8)
    seen = None
    for _ in range(25):
        time.sleep(0.6)
        look()
        cards = [(card_title(t), t) for t in texts if t[1] > 0.2]
        cards = [(n, t) for n, t in cards if n and t[1] - 0.11 > 0.18]
        if cards:
            title, t = cards[0]
            tap(t[0] + t[2] / 2, t[1] - 0.11)  # the postcard above its title
            wait("preview", timeout=6 * LAG)
            time.sleep(0.5)
            look()
            ok, got = preview_ok(title)
            if not ok:
                keep_capture("preview")
                close()
                raise Stop(f"the gift preview reads {got!r}, wanted {title!r}: nothing sent")
            if find(lambda u: "STICKER" in up(u) and u[1] < 0.7):
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
            tap_text(send)
            s = wait("friend", "picker", "preview", "unknown", timeout=8 * LAG)
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
        titles = tuple(sorted(u[4] for u in texts if u[1] > 0.2))
        if titles == seen:
            close()  # the end of the gifts, and none of ours
            raise OutOfGifts()
        seen = titles
        drag(0.75, 0.45, x=0.5 + random.uniform(-0.005, 0.005))
    raise Stop("scrolled the gift list 25 times without reaching its end")


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
    field = [t for t in texts if 0.42 < t[1] < 0.5 and "NICKNAME" not in up(t)]
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


def one_friend(row):
    """open the row's friend page, check, gift and/or tag. -> the gift sent, or None"""
    tap_text(row["t"])
    s = wait("friend", "giftpopup", timeout=8)
    if s == "giftpopup":
        close()  # their gift to me: X, never OPEN
        wait("friend", timeout=6)
    name = page_name()
    if not name or not same_name(name, row["name"]):
        log(f"  opened {name!r}, wanted {row['name']!r}: skipped")
        return None
    nick, _ = page_nickname()
    t = label("SEND GIFT")
    if not gift_icon(t):
        log(f"{name} ({nick}): their SEND GIFT is grey: skipped")
        return None
    n = meter()
    if n == 1:
        log(f"{name} ({nick}): 1 point to level up: no gift, tagging WAIT")
        rename("WAIT", nick, row["nick"])
        return None
    title = send_gift()
    log(f"{name} ({nick}): {'would send' if DRY else 'sent'} {title}")
    if n == 2:
        rename("SENT", nick, row["nick"])
    return title


# ---------- a run ----------

def run_searches(limit):
    sent, done = 0, set()
    to_list()
    set_sort()
    for first, base_q in (("iii", FIRST), ("lll", THEN)):
        for zone, zq in ZONES:
            n = search(base_q, zq)
            log(f"{first} + {zone}: ({n})")
            if not n:
                continue
            if arrow() != "down":
                set_sort()
            stale = 0
            while True:
                if look() != "friends":  # a drag that landed as a tap opened something: back first
                    to_list()
                    continue
                todo = [r for r in rows() if r["name"] not in done]
                if todo and todo[0]["badged"]:
                    break  # sorted can-receive first: from here down nobody can take a gift
                if not todo:
                    before = [r["name"] for r in rows()]
                    drag(0.75, 0.4)
                    look()
                    stale = stale + 1 if [r["name"] for r in rows()] == before else 0
                    if stale:
                        break  # the bottom of the list
                    continue
                row = todo[0]
                done.add(row["name"])
                if one_friend(row):
                    sent += 1
                    if sent >= limit:
                        log(f"{sent} gifts: the limit for this run")
                        return sent
                to_list()
    return sent


def quit_mirroring():
    subprocess.run(["osascript", "-e", 'tell application "iPhone Mirroring" to quit'], capture_output=True)


def one_phone(a):
    import home
    ui.CAP = f"/tmp/gift_{PHONE}.png"
    base.new_run_dir(None, os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S") + "-" + PHONE))
    global DRY
    DRY = a.dry_run
    if a.cmd == "look":
        s = look()
        print(f"{PHONE}: {s}  rows: {rows() if s == 'friends' else '-'}  arrow: {arrow()}")
        print("   ", summary())
        if s == "friend":
            print("    hearts:", heart_fill())
        return
    sent = 0
    try:
        s = look()
        if s in ("unknown", "blank", "map"):  # (home.start reads a scrolled friend page, SET NICKNAME, as a rename box)
            s = home.start(storage=False)
        log(f"Pokémon GO up, on {s}")
        sent = run_searches(a.limit)
        log(f"done: {sent} gifts sent" + ("" if sent >= a.limit else ", nobody left who can take one"))
    except OutOfGifts:
        log("out of Mission Walk / Mission Creek Park gifts: stopping")
        if not ui.ANDROID:
            to_list()
            quit_mirroring()
            log("closed iPhone Mirroring")
    except Stop as e:
        log(f"STOPPED: {e}")
        keep_capture("stop")
        sys.exit(1)
    except KeyboardInterrupt:
        log("interrupted")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=("run", "look"))
    ap.add_argument("--phone", choices=("ios", "android"))
    ap.add_argument("--limit", type=int, default=1000, help="at most N gifts per phone this run")
    ap.add_argument("--dry-run", action="store_true", help="everything but SEND and the nickname's OK")
    a = ap.parse_args()
    if a.phone:
        if (a.phone == "android") != ui.ANDROID:  # ui reads POGO_PHONE on import: start over with it set
            env = dict(os.environ, POGO_PHONE="android" if a.phone == "android" else "")
            sys.exit(subprocess.call([sys.executable] + sys.argv, env=env))
        return one_phone(a)
    ui.ensure_helper()  # built once here, so the two phones don't both compile it
    procs = []
    for phone in ("ios", "android"):
        env = dict(os.environ, POGO_PHONE="android" if phone == "android" else "")
        cmd = [sys.executable, os.path.abspath(__file__), a.cmd, "--phone", phone, "--limit", str(a.limit)]
        cmd += ["--dry-run"] if a.dry_run else []
        procs.append(subprocess.Popen(cmd, env=env))
    codes = [p.wait() for p in procs]
    sys.exit(max(codes))


if __name__ == "__main__":
    main()
