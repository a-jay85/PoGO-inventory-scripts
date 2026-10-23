#!/usr/bin/env python3
"""/trade: local trades between the user's two accounts, far-apart pairs only, regular trades only.

  caffeinate -dimsu python3 trade.py [--limit N] [--done N]
  caffeinate -dimsu python3 trade.py look          (what the script reads on each phone; taps nothing)

HashTagAJay plays on the iPhone (iPhone Mirroring on the Mac), CyrillJan on the Android phone (adb). Each phone is
driven by its own phone.py process. The Mac's mouse has to be left alone while it runs: iPhone Mirroring takes it.

Each round: both phones go to the other account's friend page (map -> profile -> FRIENDS -> SEARCH -> name -> X on
the gift), both tap LOCAL TRADE, each picks the newest Pokémon of a saved search (the "0-100km" / "100+km"
shortcuts), NEXT, and on the confirm screen both costs must read a regular 100 Stardust (white on blue; a special
trade shows purple on pink) and the catch spots must be 100+ km apart. Then CONFIRM on both, the result screens
are closed, and the next round starts from the friend page.
Pairs: iPhone 0-100km with Android 100+km while both have some, then iPhone 100+km with Android 0-100km. When
neither pair is left it stops. At most 99 trades a day (one is left for a special trade by hand), counted in
.state.json; --done N says N were already made today. --limit N: at most N trades this run.
Log and captures go in runs/<time>/.
"""
import argparse, datetime, json, os, random, re, shutil, statistics, subprocess, sys, time
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, log
from search import pokeball

STATE = os.path.join(HERE, ".state.json")
PER_DAY = 99  # the game allows 100: one is kept for a special trade made by hand
PER_RUN = 48  # a run makes at most this many (--limit): two runs (96) stay under PER_DAY, one leaves trades for other friends
NEAR, FAR = "0-100km", "100+km"  # the saved searches, on both accounts
QUERY = {NEAR: "giv,xlx&distance0-100", FAR: "giv,xlx&distance100-"}  # what each one puts in the bar
MIN_KM = 100
SKIPS = 3  # pairs caught under MIN_KM apart: how many of the Android's next ones to try before stopping
COST = 100  # Stardust for a regular trade between these two accounts
OK_WARNINGS = ("MAX MOVE LEVELS WILL BE RESET",)  # trade warnings tapped YES; any other one stops the run
X_BUTTON = (0.5, 0.935)  # the round X at the bottom middle (gift, result, friend page, picker)
MANAGE_X = (0.5, 0.906)  # the round X that closes the Manage Favorite Search box
SORT_BUTTON = (0.838, 0.937)


class Expired(Stop):
    """the game canceled the trade before both confirmed: nothing traded, the round can start over"""


class ServiceDown(Expired):
    """the trading server failed ("Trading service temporarily unavailable"): restart the game on both phones"""


# ---------- the two phones ----------

class Phone:
    def __init__(self, name, android, account, friend):
        self.name, self.account, self.friend = name, account, friend
        env = dict(os.environ)
        env.pop("POGO_PHONE", None)
        if android:
            env["POGO_PHONE"] = "android"
        self.proc = subprocess.Popen([sys.executable, os.path.join(HERE, "phone.py"), name], env=env, text=True,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.texts, self.path, self.screen = [], None, "?"
        self.live = False  # in a trade: from here an "expired" box means start the trade over

    def call(self, **req):
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise Stop(f"{self.name}: its phone process ended")
        out = json.loads(line)
        if "error" in out:
            raise Stop(f"{self.name}: {out['error']}")
        return out

    def look(self):
        out = self.call(op="look")
        self.texts = [tuple(t) for t in out["texts"]]
        self.path = out["path"]
        self.screen = classify(self.texts, self.path)
        if self.live and self.screen == "expired":
            self.live = False
            self.expired()
        return self.screen

    def tap(self, fx, fy, fuzz=0.008):
        self.call(op="tap", fx=fx + random.uniform(-fuzz, fuzz), fy=fy + random.uniform(-fuzz / 2, fuzz / 2))
        time.sleep(random.uniform(0.15, 0.3))

    def tap_text(self, t, dy=0.0):
        x, y, w, h, _ = t
        self.tap(x + w / 2, y + h / 2 + dy, fuzz=min(0.008, w / 4))

    def type(self, text):
        self.call(op="type", text=text)

    def key(self, name):
        self.call(op="key", name=name)

    def wait(self, *screens, timeout=10):
        end = time.time() + timeout
        grace = end + 30  # a blank loading screen (the server is slow) holds the timeout off, this long at most
        while True:
            if self.look() in screens:
                return self.screen
            if self.screen == "expired":
                self.expired()
            if time.time() > end and not (self.screen == "blank" and time.time() < grace):
                raise Stop(f"{self.name}: wanted {'/'.join(screens)}, screen is {self.screen}: {self.summary()}")
            time.sleep(0.3)

    def expired(self):
        if self.find(lambda t: "UNAVAILABLE" in up(t) or "ERROR FETCHING" in up(t)):
            raise ServiceDown(f"{self.name}: the trading service failed: {self.summary()}")
        raise Expired(f"{self.name}: the trade expired")

    def restart(self):
        self.call(op="restart")
        self.live = False

    def start(self):
        """Pokémon GO open and loaded, from wherever the phone is (closed too)"""
        return self.call(op="start", run_dir=base.RUN_DIR)["screen"]

    def unstick(self, backs):
        """one step out of a screen nobody knows: Android Back, iPhone reopens the game (once).
        backs: how many this trip to the friend page took already"""
        self.call(op="unstick", texts=[list(t) for t in self.texts], backs=backs)

    def find(self, pred):
        return [t for t in self.texts if pred(t)]

    def summary(self):
        return " | ".join(t[4] for t in self.texts)[:250]

    def keep(self, tag):
        if self.path and os.path.exists(self.path):
            os.makedirs(base.RUN_DIR, exist_ok=True)
            shutil.copy(self.path, os.path.join(base.RUN_DIR, f"{time.strftime('%H%M%S')}-{self.name}-{tag}.png"))

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


# ---------- reading screens ----------

def up(t):
    return t[4].upper().strip()


def classify(texts, path):
    raw = [up(t) for t in texts]
    words = {ui.norm(t[4]) for t in texts}
    joined = " ".join(raw)
    if "MANAGE FAVORITE" in joined:
        return "manage"  # the Manage Favorite Search box: a shortcut tap that landed as a long press
    if "EXIT POK" in joined:
        return "exit"  # Android: "Do you want to exit Pokémon GO?"
    if "TRADE EXPIRED" in joined or "TRADE WAS CANCELED" in joined or "HAS EXPIRED" in joined:
        return "expired"  # a trade left open too long (or the other side left): OK
    if "ERROR FETCHING TRADE" in joined or "TRADING SERVICE" in joined:
        return "expired"  # the server lost the trade ("Trading service temporarily unavailable"): OK, start over
    if "CANCEL THIS TRADE" in joined:
        return "leave"  # "Do you want to cancel this trade?" after the exit door: YES / NO
    if "ARE YOU SURE YOU WANT TO TRADE" in joined:
        return "warning"
    if confirm_label(texts) and any(re.search(r"\d\s*KM$", r) for r in raw):
        return "confirm"
    if "RECENT" in words and any(w.startswith("COMBAT POWER") for w in words):
        return "sortmenu"  # the picker's sort menu
    if "WAITING FOR" in joined and "TRADING" in joined:
        return "waiting"
    if re.search(r"\bME LV", joined):
        return "lobby"  # in the trade, nothing picked: "Waiting for ... to select their Pokémon", picker button below
    # the trade's Pokémon list: only a POKÉMON header (storage has TAGS and EGGS tabs beside it). The SPECIAL TRADES
    # REMAINING line shows only while no search is on: the picker keeps the last search between trades. A pile
    # search can leave fewer than 3 tiles, or none: then the distance search in the bar vouches for it
    if "SPECIAL TRADES REMAINING" in joined or "POKMON" in words and not words & {"TAGS", "EGGS"} and (
            sum(bool(re.fullmatch(r"CP\s*\d+", r.replace("С", "C"))) for r in raw) >= 3 or "FAVORITE" in words
            or "DISTANCE" in joined):
        return "picker"
    if "NEXT" in words and any(re.search(r"CP\s*\d+\s*>", r) for r in raw):
        return "select"
    if "STARDUST" in words and ("POWER UP" in words or any("CANDY" in w for w in words)):
        return "result"
    if "SEND GIFT" in words and "LOCAL" in words:
        return "friend"
    if "OPEN" in words and ("GREETINGS FROM" in joined or "SENT" in joined):
        return "gift"
    if "ADD FRIEND" in words or "INVITE" in words and "FRIENDS" in words:
        return "friends"
    if "ME" in words and "FRIENDS" in words:
        return "profile"
    if len(texts) <= 12 and pokeball(path):
        return "map"
    if all(t[1] < 0.08 for t in texts):
        return "blank"  # only the status bar: the game is loading
    return "unknown"


def confirm_label(texts):
    """the CONFIRM button (CANCEL once tapped), left of the middle"""
    for t in texts:
        if t[0] < 0.3 and 0.45 < t[1] < 0.6 and ui.norm(t[4]) in ("CONFIRM", "CANCEL"):
            return t
    return None


def friend_name(p):
    """the name at the top left of a friend page"""
    top = [t for t in p.texts if t[1] < 0.16 and t[0] < 0.2 and re.fullmatch(r"[A-Za-z0-9]{3,}", t[4].strip())]
    return top[0][4].strip() if top else None


def label(p, name):
    hits = p.find(lambda t: ui.norm(t[4]) == name)
    return hits[0] if hits else None


# ---------- getting to the friend page ----------

def to_friend(p):
    p.live = False
    unknown, backs = 0, 0
    for _ in range(40):  # room for a few Backs out of popups
        s = p.look()
        unknown = unknown + 1 if s == "unknown" else 0
        if s == "friend":
            name = friend_name(p)
            if name and name.lower() == p.friend.lower():
                return
            log(f"{p.name}: on {name}'s page, not {p.friend}'s: closing it")
            p.tap(*X_BUTTON)
        elif s in ("exit", "expired"):
            button = label(p, "CANCEL" if s == "exit" else "OK")
            if not button and s == "expired":
                # the iPhone's "This trade with ... has expired." box: OCR can miss its white-on-green OK, which
                # sits just under the message
                msg = p.find(lambda t: "HAS EXPIRED" in up(t))
                if msg:
                    p.tap(0.5, msg[0][1] + 0.077)
                    time.sleep(1)
                    continue
            if not button:
                raise Stop(f"{p.name}: {s} dialog without its button: {p.summary()}")
            p.tap_text(button)
            if p.find(lambda t: "UNAVAILABLE" in up(t)):
                raise ServiceDown(f"{p.name}: the trading service is down")
        elif s == "leave":
            p.tap_text(label(p, "YES"))
        elif s == "manage":
            p.tap(*MANAGE_X)
        elif s in ("gift", "result"):
            p.tap(*X_BUTTON)
        elif s == "map":
            p.tap(0.13, 0.91)
        elif s in ("profile", "friends"):
            # a typed search hides ADD FRIEND, so a searched friend list reads as "profile": tap the row if it's there
            row = p.find(lambda t: t[4].strip().lower() == p.friend.lower() and t[0] > 0.2 and t[1] > 0.25)
            if row:
                p.tap_text(row[0], dy=0.01)
            elif s == "profile":
                p.tap_text(label(p, "FRIENDS"))
            else:
                search = label(p, "SEARCH")
                if not search:
                    raise Stop(f"{p.name}: friend list without SEARCH: {p.summary()}")
                p.tap_text(search, dy=-0.035)
                time.sleep(1.2)
                p.type(p.friend)
                p.key("return")
        elif s == "sortmenu":
            p.tap_text(label(p, "RECENT"))  # closes it (sort_recent fixes the order later)
        elif s == "picker":
            p.tap(*X_BUTTON)  # back to the trade's lobby
        elif s in ("lobby", "waiting"):
            p.tap(0.09, 0.115)  # the exit door, top left: leave the trade
        elif s in ("select", "warning", "confirm"):
            p.keep("midtrade")
            raise Stop(f"{p.name}: in the middle of a trade ({s}): finish or back out of it by hand")
        elif s == "unknown":
            if unknown > 2:  # three unknown looks running: a popup, or a screen trading doesn't use
                p.keep("lost")
                p.unstick(backs)  # stops the run once it's out of steps
                unknown, backs = 0, backs + 1
        time.sleep(1.5)
    p.keep("lost")
    raise Stop(f"{p.name}: couldn't get to {p.friend}'s friend page")


def open_trade(phones):
    """LOCAL TRADE on both. The first one waits ("Waiting for ... to be available") until the second one taps too"""
    for p in phones:
        for attempt in range(4):
            s = p.wait("friend", "waiting", "picker", "expired", timeout=8)  # (a banner can cover it for a moment)
            if s == "expired":  # the box from an old trade can come up late, on the friend page
                to_friend(p)
                continue
            if s != "friend":
                break
            t = label(p, "LOCAL")
            if attempt == 3 or not t:
                raise Stop(f"{p.name}: LOCAL TRADE didn't open: {p.summary()}")
            p.tap_text(t, dy=-0.035)  # the round icon above the label
            for _ in range(10):  # the iPhone can take a few seconds to leave the page
                time.sleep(0.6)
                if p.look() != "friend":
                    break
    try:
        for p in phones:
            p.wait("picker", timeout=20)
    except Stop:
        if not all(p.look() in ("waiting", "expired") for p in phones):
            raise
        # the server never joined the two: each waits for the other, or one has "Trading service unavailable" up.
        # Leave on a waiting phone, or the next round's to_friend skips it and it waits again
        for p in phones:
            if p.screen == "waiting":
                p.tap(0.09, 0.115)  # the exit door
        raise ServiceDown("the trading service didn't join the two phones")


IN_TRADE = ("picker", "lobby", "sortmenu")


def to_picker(p):
    for _ in range(6):
        s = p.look()
        if s == "picker":
            return
        if s == "sortmenu":
            p.tap_text(label(p, "RECENT"))  # closes it (sort_recent fixes the order later)
        elif s == "lobby":
            p.tap(0.5, 0.932)  # the Pokémon button at the bottom
        else:
            break
        time.sleep(1.5)
    raise Stop(f"{p.name}: couldn't get back to the Pokémon list: {p.summary()}")


def specials_left(p):
    for t in p.texts:
        m = re.search(r"SPECIAL TRADES REMAINING\W*(\d+)", up(t))
        if m:
            return int(m.group(1))
    return None


# ---------- the picker ----------

def open_panel(p):
    """the search panel with the saved shortcuts. Android: the keyboard comes up over them and is put away"""
    for attempt in range(3):
        if not label(p, "FAVORITE"):
            p.tap(0.5, 0.18)
            time.sleep(1.2)
            p.look()
        keyboard = p.find(lambda t: up(t) in ("?123", "OK") and t[1] > 0.5)
        if keyboard and p.name == "android":
            p.key("back")  # Android: hides the keyboard only, the panel stays
            time.sleep(1.0)
            p.look()
        if label(p, "FAVORITE") and shortcut(p, NEAR) and shortcut(p, FAR):
            return
    p.keep("panel")
    raise Stop(f"{p.name}: the search panel with the saved shortcuts didn't show: {p.summary()}")


def shortcut(p, name):
    hits = p.find(lambda t: t[4].strip().lower() == name.lower())
    return hits[0] if hits else None


def shortcut_count(p, name):
    t = shortcut(p, name)
    below = p.find(lambda u: t[1] + 0.01 < u[1] < t[1] + 0.06 and abs((u[0] + u[2] / 2) - (t[0] + t[2] / 2)) < 0.08
                   and re.fullmatch(r"[\d,]+", u[4].strip()))
    return int(below[0][4].replace(",", "")) if below else None


def counts(p, last=None):
    """{NEAR: n, FAR: n} off the open panel, read twice the same. The reader often misses a lone digit under a
    shortcut ('6', every '0'). Then: the bar's pile is the '(n)' in the header, the game's own count; the other
    pile is what last held for it (the previous round's read), or, at a run's start, what its search shows.
    last is updated with what was read"""
    seen = None
    for _ in range(4):
        got = {n: shortcut_count(p, n) for n in (NEAR, FAR)}
        for n in got:
            if got[n] is None and shortcut(p, n):
                if in_bar(p, n):
                    got[n] = results(p)
                elif last and n in last:
                    got[n] = last[n]
                else:
                    got[n] = probe(p, n)
                    if last is not None:
                        last[n] = got[n]
        if None not in got.values() and got == seen:
            if last is not None:
                last.update(got)
            return got
        seen = got
        time.sleep(0.3)
        p.look()
    raise Stop(f"{p.name}: couldn't read the shortcut counts: {p.summary()}")


def long_pressed(p, pile):
    """the shortcut tap landed as a long press: the Manage Favorite Search box is up and the panel stays open.
    Close it and tap the shortcut again. True when it did"""
    if not p.find(lambda t: "MANAGE FAVORITE" in up(t)):
        return False
    log(f"{p.name}: the shortcut tap was a long press: tapping again")
    p.tap(*MANAGE_X)
    time.sleep(1)
    p.look()
    p.tap_text(shortcut(p, pile), dy=-0.055)
    return True


def probe(p, pile):
    """run a pile's search to read its '(n)' off the header (0 too), then open the panel again"""
    p.tap_text(shortcut(p, pile), dy=-0.055)
    for _ in range(12):
        time.sleep(0.4)
        p.look()
        if long_pressed(p, pile):
            continue
        if p.screen == "picker" and not label(p, "FAVORITE") and in_bar(p, pile) and results(p) is not None:
            n = results(p)
            log(f"{p.name}: {pile} count missed under its shortcut: its search shows {n}")
            open_panel(p)
            return n
    p.keep("probe")
    raise Stop(f"{p.name}: couldn't read the {pile} count: {bar(p)!r}, {p.summary()}")


def bar(p):
    for t in p.texts:
        s = re.sub(r"\s", "", t[4]).lower()
        if t[1] < 0.24 and "distance" in s:
            return s
    return None


def results(p):
    for t in p.texts:
        m = re.search(r"\((\d[\d,]*)\)", t[4])
        if m and t[1] < 0.14:
            return int(m.group(1).replace(",", ""))
    return None


def same_l(s):
    """OCR mixes up l, i, I, 1 and | in the bar ('xix' for 'xlx'): the two queries differ elsewhere"""
    return re.sub(r"[il1|]", "l", s.lower())


def in_bar(p, pile):
    """the bar shows exactly this pile's search. OCR can miss the far pile's last '-': the two piles still differ
    without it ('&distance100' is no tail of '&distance0-100')"""
    got, want = same_l(bar(p) or "").rstrip("-"), same_l(QUERY[pile]).rstrip("-")
    return got.endswith(want) and len(got) - len(want) <= 2


def pick_pile(p, pile):
    """tap the saved search and check the bar shows exactly it, with results"""
    t = shortcut(p, pile)
    p.tap_text(t, dy=-0.055)  # the round button above the label
    for _ in range(12):
        time.sleep(0.4)
        p.look()
        if long_pressed(p, pile):
            continue
        if p.screen == "picker" and not label(p, "FAVORITE"):  # the panel closed and the search ran
            if in_bar(p, pile) and results(p):
                return results(p)
    p.keep("search")
    raise Stop(f"{p.name}: the search bar doesn't show {QUERY[pile]}: {bar(p)!r}, {p.summary()}")


def arrow(path):
    """'down' (newest first) / 'up' / None: the small arrow on the sort button, light teal on dark teal"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    light = {(x, y) for x in range(int(W * .86), int(W * .99)) for y in range(int(H * .89), int(H * .98))
             if im.getpixel((x, y))[0] >= 120 and min(im.getpixel((x, y))) <= 200}
    seen, found = set(), []
    for p in light:  # the arrow is a blob of its own, about 8-10 px square (Pixel and iPhone captures)
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
            found.append((blob, min(ys), h))
    if len(found) != 1:
        return None
    blob, top, h = found[0]
    head_up = sum(1 for x, y in blob if y < top + h / 3)
    head_down = sum(1 for x, y in blob if y >= top + 2 * h / 3)
    return "up" if head_up > head_down else "down" if head_down > head_up else None


def sort_recent(p):
    """Recent, newest first. Picking RECENT when it's already the sort flips the order, so: pick it, read the
    arrow, and pick it once more if it points up"""
    for attempt in range(3):
        p.tap(*SORT_BUTTON, fuzz=0.005)
        for _ in range(10):
            time.sleep(0.3)
            p.look()
            recent = next((t for t in p.texts if ui.norm(t[4]) == "RECENT" and t[1] > 0.3), None)
            if recent and p.find(lambda t: ui.norm(t[4]).startswith("COMBAT POWER")):
                break
        else:
            raise Stop(f"{p.name}: the sort menu didn't open: {p.summary()}")
        p.tap_text(recent)
        for _ in range(12):
            time.sleep(0.3)
            if p.look() == "picker" and not p.find(lambda t: ui.norm(t[4]).startswith("COMBAT POWER")):
                break
        time.sleep(0.5)
        p.look()
        way = arrow(p.path)
        if way == "down":
            log(f"{p.name}: sorted Recent, newest first")
            return
        log(f"{p.name}: sort arrow reads {way}: RECENT again")
    p.keep("sort")
    raise Stop(f"{p.name}: couldn't get the list sorted Recent, newest first")


def tile(p, i=0):
    """the results' i-th tile in reading order (0: top left): its CP line"""
    cps = p.find(lambda t: t[1] > 0.22 and re.fullmatch(r"CP\s*\d+", t[4].strip().upper().replace("С", "C")))
    rows = []
    for t in sorted(cps, key=lambda t: t[1]):
        if rows and t[1] < rows[-1][0][1] + 0.03:
            rows[-1].append(t)
        else:
            rows.append([t])
    order = [t for row in rows for t in sorted(row, key=lambda t: t[0])]
    if len(order) <= i:
        raise Stop(f"{p.name}: no tile {i + 1} in the results: {p.summary()}")
    return order[i]


def choose(p, i=0):
    """tile i -> its screen -> NEXT (-> YES on a known warning) -> the confirm screen. -> its name"""
    p.tap_text(tile(p, i), dy=0.06)
    p.wait("select", timeout=8)
    name = next((t[4] for t in sorted(p.texts, key=lambda t: t[1]) if t[1] > 0.09 and t[0] < 0.3), "?")
    cp = next((up(t) for t in p.texts if re.search(r"CP\s*\d+\s*>", up(t))), "")
    log(f"{p.name}: {name.strip()} {cp.split('>')[0].strip()}")
    for attempt in range(3):
        nxt = label(p, "NEXT")
        if nxt:
            p.tap_text(nxt)
        s = p.wait("select", "warning", "confirm", "lobby", timeout=6)
        for _ in range(8):
            if s != "select":
                break
            time.sleep(0.4)
            s = p.look()
        if s == "warning":
            warning(p)
            s = p.wait("confirm", "lobby", timeout=8)
        if s == "confirm" or s == "lobby" and any(re.search(r"CP\s*\d+\s*-\s*\d+", up(t)) for t in p.texts):
            return name.strip()  # (lobby: picked, waiting for the other side to pick)
    raise Stop(f"{p.name}: NEXT didn't lead to the confirm screen: {p.summary()}")


def warning(p):
    """'Are you sure you want to trade this Pokémon?' plus the reasons: YES only if every reason is a known one"""
    top = next(t[1] for t in p.texts if "ARE YOU SURE" in up(t))
    yes = label(p, "YES")
    if not yes:
        raise Stop(f"{p.name}: trade warning without YES: {p.summary()}")
    lines = [re.sub(r"^[^A-Z]+", "", up(t)) for t in p.texts if top < t[1] < yes[1] - 0.01]
    reasons = [l for l in lines if l and "ARE YOU SURE" not in l and not l.startswith("THIS POK")]
    # (the bullet in front can read as a stray letter: "X MAX MOVE ...")
    unknown = [r for r in reasons if not any(r.startswith(k) or re.sub(r"^\S\s+", "", r).startswith(k)
                                             for k in OK_WARNINGS)]
    if not reasons or unknown:
        p.keep("warning")
        raise Stop(f"{p.name}: a trade warning I don't know: {reasons or p.summary()}")
    log(f"{p.name}: warning ({'; '.join(reasons)}): YES")
    p.tap_text(yes)


# ---------- the confirm screen ----------

def cost_ok(p):
    """-> (ok, what was read). Regular: '100' (the Stardust icon may read as one stray letter), white digits on a
    blue box. A special trade: a bigger number, purple digits on a pale pink box"""
    box = next((t for t in p.texts if 0.3 < t[0] < 0.55 and 0.47 < t[1] < 0.56 and re.search(r"\d", t[4])), None)
    if not box:
        return False, "no cost read"
    text = box[4].strip()
    if not re.fullmatch(r"(?:\S\s*)?%d" % COST, text) or re.fullmatch(r"\d{2,}", text) and text != str(COST):
        return False, f"cost {text!r}"
    im = Image.open(p.path).convert("RGB")
    W, H = im.size
    x, y, w, h = box[:4]
    region = [im.getpixel((i, j)) for i in range(int((x + w * 0.4) * W), int((x + w) * W))
              for j in range(int(y * H), int((y + h) * H))]
    if not region:
        return False, "cost box empty"
    med = tuple(int(statistics.median(c)) for c in zip(*region))
    purple = sum(1 for r, g, b in region if r > 150 and b > 150 and g < 120)
    if not (med[2] > med[0] + 40 and med[0] < 180) or purple > 3:
        return False, f"cost {text!r} in the wrong colours (box {med}, {purple} purple pixels): special trade?"
    return True, f"cost {text!r}"


def km(p):
    for t in p.texts:
        m = re.search(r"([\d,]+(?:\.\d+)?)\s*km", t[4], re.I)
        if m and 0.48 < t[1] < 0.6:
            return float(m.group(1).replace(",", ""))
    return None


def check_confirm(p):
    """three tries at a clean read: a regular cost and the catch spots far enough apart"""
    why = ""
    p.wait("confirm", timeout=20)  # the first to pick waits in the lobby for the other
    for _ in range(3):
        if p.look() == "confirm":
            ok, why = cost_ok(p)
            d = km(p)
            if ok and d is not None:
                candy = next((up(t) for t in p.texts if re.fullmatch(r"\+\d", up(t))), "?")
                return d, candy
            why += f", {d} km"
        time.sleep(0.5)
    p.keep("confirm")
    raise Stop(f"{p.name}: won't confirm: {why}")


def confirm(p):
    """CONFIRM once. Once it lands the button reads CANCEL in the same spot: only tap again while it says CONFIRM"""
    for attempt in range(4):
        t = confirm_label(p.texts) if p.screen == "confirm" else None
        if not t:
            return  # the trade animation has started
        if ui.norm(t[4]) == "CANCEL":
            return
        if attempt:
            log(f"{p.name}: CONFIRM didn't land, again")
        p.tap_text(t)
        for _ in range(6):
            time.sleep(0.4)
            p.look()
            t = confirm_label(p.texts) if p.screen == "confirm" else None
            if not t or ui.norm(t[4]) == "CANCEL":
                return
    raise Stop(f"{p.name}: CONFIRM wouldn't take")


# ---------- the day's count ----------

def today():
    return datetime.date.today().isoformat()


def made_today():
    try:
        s = json.load(open(STATE))
    except (OSError, ValueError):
        return 0
    return s.get("count", 0) if s.get("date") == today() else 0


def set_made(n):
    with open(STATE, "w") as f:
        json.dump({"date": today(), "count": n}, f)


# ---------- a run ----------

def pairs(ios, android):
    """which pile on which phone: iPhone 0-100km + Android 100+km first, then the other way round"""
    if ios[NEAR] and android[FAR]:
        return NEAR, FAR
    if ios[FAR] and android[NEAR]:
        return FAR, NEAR
    return None


def trade_once(ios, android, specials):
    """one trade. specials: what the run remembers between trades (special trades left, phones already sorted)"""
    phones = (ios, android)
    if all(p.look() in IN_TRADE for p in phones):
        for p in phones:  # both still in a trade from before: carry on in it
            to_picker(p)
    else:
        for p in phones:
            if p.look() != "waiting":  # waiting already: LOCAL TRADE on the other phone lets it in
                to_friend(p)
        open_trade(phones)
    for p in phones:
        p.live = True
    for p in phones:
        n = specials_left(p)  # (not shown while a search is on)
        if n is None:
            continue
        if p.name in specials and n < specials[p.name]:
            raise Stop(f"{p.name}: special trades left went from {specials[p.name]} to {n}")
        specials.setdefault(p.name, n)
    piles = specials.setdefault("piles", {})
    for p in phones:
        piles.setdefault(p.name, {})
    # after the first round the counts are known: each pick reads its pile's '(n)' and the trade takes one off.
    # Read them off the panel again only when a pile the pair needs could be down to its last one
    pair = pairs(piles["ios"], piles["android"]) if all(len(piles[p.name]) == 2 for p in phones) else None
    if not (pair and piles["ios"][pair[0]] >= 2 and piles["android"][pair[1]] >= 2):
        have = {}
        for p in phones:
            open_panel(p)
            have[p.name] = counts(p, piles[p.name])
        log(f"piles: iPhone {have['ios']}, Android {have['android']}")
        pair = pairs(have["ios"], have["android"])
        if not pair:
            return None  # both phones are left in the picker: nothing picked, nothing to undo
    for p, pile in zip(phones, pair):
        p.look()
        # the last trade's search stays on in the list: its header has the count, no need to run it again
        n = results(p) if p.screen == "picker" and not label(p, "FAVORITE") and in_bar(p, pile) else None
        if not n:
            open_panel(p)
            n = pick_pile(p, pile)
        piles[p.name][pile] = n - 1  # what's left once this trade goes through
        log(f"{p.name}: {pile} ({n})")
        if p.name not in specials.setdefault("sorted", []):  # once a run: the sort stays put between trades
            sort_recent(p)
            specials["sorted"].append(p.name)
        elif arrow(p.path) != "down":
            sort_recent(p)
    got = [choose(p) for p in phones]
    for skip in range(SKIPS + 1):
        reads = [check_confirm(p) for p in phones]
        d = reads[0][0]
        if abs(reads[0][0] - reads[1][0]) > 1:
            raise Stop(f"the phones read different distances: {reads}")
        if d >= MIN_KM:
            break
        if skip == SKIPS:
            raise Stop(f"still under {MIN_KM} km after skipping {SKIPS} of the Android's: nothing confirmed")
        # too close: the Android puts its pick back and offers its next one instead
        log(f"{got[0]} and {got[1]} were caught only {d} km apart: Android tries its next one")
        android.tap(0.5, 0.932)  # change Pokémon: back to the list, search kept
        android.wait("picker", timeout=10)
        got[1] = choose(android, skip + 1)
    for p in (android, ios):  # the Android side first: its taps never miss, the iPhone's last tap starts the trade
        p.look()
        if p.screen != "confirm":
            raise Stop(f"{p.name}: left the confirm screen before CONFIRM: {p.summary()}")
        confirm(p)
    for p in phones:
        p.live = False  # confirmed: an "expired" box from here on comes after the trade, it doesn't undo it
    return got, d, reads[0][1]


def finish(phones):
    """wait out the animation, read what each got, close the result screens"""
    for p in phones:
        if p.wait("result", "expired", timeout=45) == "expired":
            # seen on the Android once, while the iPhone got its Pokémon: the trade went through all the same
            log(f"{p.name}: says the trade expired after both confirmed: the next round clears it")
    for p in phones:
        for _ in range(3):
            if p.screen != "result":
                break
            p.tap(*X_BUTTON)
            time.sleep(1.5)
            if p.look() != "result":
                break


def restart(phones):
    """force-close and open the game on both, then wait until each is past the loading screens"""
    for p in phones:
        p.restart()
    for p in phones:
        end = time.time() + 120
        while p.look() in ("unknown", "blank"):  # loading screens and their tips
            if time.time() > end:
                p.keep("restart")
                raise Stop(f"{p.name}: the game didn't load after the restart: {p.summary()}")
            time.sleep(3)
    log("both phones restarted")


def cmd_look(phones):
    for p in phones:
        s = p.look()
        print(f"{p.name} ({p.account}): {s}")
        print("   ", p.summary())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=("run", "look", "restart"))
    ap.add_argument("--limit", type=int, default=PER_RUN)
    ap.add_argument("--done", type=int, help="trades already made today (sets the day's count)")
    a = ap.parse_args()
    ios = Phone("ios", False, "HashTagAJay", "CyrillJan")
    android = Phone("android", True, "CyrillJan", "HashTagAJay")
    phones = (ios, android)
    try:
        if a.cmd == "look":
            return cmd_look(phones)
        base.new_run_dir(os.path.join(HERE, "runs"))
        if a.cmd == "restart":
            return restart(phones)
        for p in phones:  # from wherever each phone is, Pokémon GO closed too
            log(f"{p.name}: Pokémon GO up, on {p.start()}")
        if a.done is not None:
            set_made(a.done)
        made, n, specials, expired = made_today(), 0, {}, 0
        log(f"{made} trades made today so far, {PER_DAY} a day; this run: at most {a.limit}")
        while n < a.limit:
            if made_today() >= PER_DAY:
                log(f"{PER_DAY} trades today: done for the day")
                break
            try:
                got = trade_once(ios, android, specials)
            except Expired as e:
                expired += 1
                if expired > 3:
                    raise Stop(f"{e}, {expired} times in a row")
                if isinstance(e, ServiceDown):  # closing and opening the game often clears it
                    log(f"{e}: restarting Pokémon GO on both phones")
                    restart(phones)
                else:
                    log(f"{e}: starting the round over")
                continue
            expired = 0
            if not got:
                log("no far-apart pairs left: done")
                break
            set_made(made_today() + 1)  # counted once both have confirmed: a missed result screen never undercounts
            n += 1
            finish(phones)
            names, d, candy = got
            log(f"trade {made_today()} today: {names[0]} (iPhone) <-> {names[1]} (Android), {d:,.1f} km, {candy} candy")
        log(f"{n} trades this run, {made_today()} today")
    except Stop as e:
        log(f"STOPPED: {e}")
        for p in phones:
            p.keep("stop")
        sys.exit(1)
    except KeyboardInterrupt:
        log("interrupted")
        sys.exit(1)
    finally:
        for p in phones:
            p.close()


if __name__ == "__main__":
    main()
