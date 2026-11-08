#!/usr/bin/env python3
"""/trade: local trades between the user's two accounts, regular trades only.

  caffeinate -dimsu python3 trade.py [--limit N] [--done N]
  caffeinate -dimsu python3 trade.py look          (what the script reads on each phone; taps nothing)
  caffeinate -dimsu python3 trade.py restart       (force-close and reopen Pokémon GO on both phones; trades nothing)
  caffeinate -dimsu python3 trade.py --rehearse N  (N rounds up to the confirm screen, never confirmed: for timing)

HashTagAJay plays on the iPhone (iPhone Mirroring on the Mac), CyrillJan on the Android phone (adb). Each phone is
driven by its own phone.py process. A touch on the Mac pauses the iPhone's side until the Mac has been idle 5 s (base.yield_to_user).

Each round: both phones go to the other account's friend page (map -> profile -> FRIENDS -> SEARCH -> name -> X on
the gift), both tap LOCAL TRADE, each picks the newest Pokémon of a search (the saved "0-100km" / "100+km"
shortcuts, or one of them typed with '&countcandy0-2499' added), NEXT, and on the confirm screen both costs must read
a regular 100 Stardust, 80 on a Friday (white on blue; a special trade shows purple on pink) and, for a far-apart pair, the catch
spots must be 100+ km apart. Then CONFIRM on both. Each phone goes at its own speed: it picks as soon as its own search
is on, and closes its result screen and taps LOCAL TRADE again as soon as its result screen shows.
Each account gets a trade's candy for the Pokémon it sends. A far-apart pair (one 0-100km, one 100+km) gives the
most, so it goes where the candy is needed (under 2,500): PLANS, first one with Pokémon left on both phones wins.
When only 0-100km ones are left on both, they're traded with each other, the species with 2,500+ candy first. Then it stops, and the 100+km ones are kept
for another day. At most 99 trades a day (one is left for a special trade by hand), counted in .state.json;
--done N says N were already made today. --limit N: at most N trades this run (default 48).
Fridays are Friendship Fridays: every trade gives 2 Candy XL and double the lucky odds, so a Friday run trades only
the ones tagged 2XL, on both phones. The rules above stay, with #2xl in place of giv,xlx. No GIV or XLX on a Friday,
and no 2XL any other day. A regular trade costs 80 Stardust on a Friday (20% off). A run stops at midnight if that
changes what it may trade.
Log and captures go in runs/<time>/.

Keep both phones on and both games open. A long pause on the iPhone during a trade can let the game's trade timer run
out: that round starts over. Trades made by hand aren't counted: pass --done N. Two runs of the default 48 come to 96.
The picker keeps the last search: when the bar already shows the one it wants, it isn't typed again.
A failing trading service or an expired trade backs both phones out to the friend page and starts the round over,
with no game restart; after 4 failures in a row it stops. If the special trades left go down during a run, it stops.
"""
import argparse, datetime, json, os, random, re, shutil, statistics, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log
from search import pokeball, amp_as_8
from home import main_menu
from session import TROUBLE
import popups, pages

STATE = os.path.join(HERE, ".state.json")
PER_DAY = 99  # the game allows 100: one is kept for a special trade made by hand
PER_RUN = 48  # a run makes at most this many (--limit): two runs (96) stay under PER_DAY, one leaves trades for other friends
NEED = "&countcandy0-2499"  # typed after a pile: only species this account has under 2,500 candy of


def set_piles(tags, saved):
    """what this run trades: the two piles (their saved searches, on both accounts, if they have them) and PLANS.
    NEAR: 0-100 km, FAR: 100+ km. RICH_I, RICH_A: the 0-100km ones of species this account has 2,500+ candy of. A long
    search doesn't fit in the bar: the iPhone shows its end, the Pixel its first ~30 characters. So the candy part goes
    last on the iPhone and right after the distance on the Pixel: NEAR + NEED and NEAR + "&countcandy2500-" look the
    same for 30 characters.
    PLANS: (iPhone search, Android search, why), in order: the first with Pokémon left on both phones is traded. Each
    account gets candy for the one it sends, so a needy search keeps the far-apart bonus for species that account needs.
    0-100km with 0-100km trades the 2,500+ candy ones first: the needy 0-100km ones are kept for a far-apart pair later"""
    global NEAR, FAR, SAVED, RICH_I, RICH_A, PLANS
    NEAR, FAR = f"{tags}&distance0-100", f"{tags}&distance100-"
    SAVED = {NEAR: "0-100km", FAR: "100+km"} if saved else {}
    RICH_I = NEAR + "&countcandy2500-"
    RICH_A = f"distance0-100&countcandy2500-&{tags}"
    PLANS = [(NEAR + NEED, FAR + NEED, "both need the candy"), (FAR + NEED, NEAR + NEED, "both need the candy"),
             (NEAR + NEED, FAR, "HashTagAJay needs the candy"), (FAR + NEED, NEAR, "HashTagAJay needs the candy"),
             (NEAR, FAR + NEED, "CyrillJan needs the candy"), (FAR, NEAR + NEED, "CyrillJan needs the candy"),
             (RICH_I, RICH_A, "0-100km with 0-100km, both 2,500+ candy"),
             (RICH_I, NEAR, "0-100km with 0-100km, HashTagAJay's 2,500+ candy"),
             (NEAR, RICH_A, "0-100km with 0-100km, CyrillJan's 2,500+ candy"),
             (NEAR, NEAR, "0-100km with 0-100km")]  # no far-apart bonus: the 100+km ones are kept for another day


set_piles("giv,xlx", saved=True)  # main() switches a Friday run to #2xl, typed


def friendship_friday():
    return datetime.date.today().weekday() == 4


MIN_KM = 100
EARTH_KM = 20040  # the farthest two spots on Earth can be apart
SKIPS = 3  # pairs caught under MIN_KM apart: how many of the Android's next ones to try before stopping
COST = 100  # Stardust for a regular trade between these two accounts
COST_READS = {"100"}  # all digits, and still this cost
FRIDAY_COST, FRIDAY_READS = 80, {"80", "180"}  # 20% off on Fridays. (The iPhone reads the Stardust icon as a 1: 180)
OK_WARNINGS = ("MAX MOVE LEVELS WILL BE RESET", "MEGA LEVEL WILL BE RESET")  # (mega level: user OK, 2026-11-07); trade warnings tapped YES; any other one stops the run
X_BUTTON = (0.5, 0.935)  # the round X at the bottom middle (gift, result, friend page, picker)
SORT_BUTTON = (0.838, 0.937)
TAPS = 9  # how many times to tap LOCAL TRADE before stopping: 5 s, then 10 s apart (~85 s in all)
IN_TRADE = ("picker", "lobby", "sortmenu")


class Expired(Stop):
    """the game canceled the trade before both confirmed: nothing traded, the round can start over"""


class ServiceDown(Expired):
    """the trading server failed ("Trading service temporarily unavailable"): the round starts over"""


class OutOfRange(Expired):
    """"... is out of range for trading" after LOCAL TRADE, with the phones side by side: nothing traded. The next
    round taps its OK and LOCAL TRADE again. main() stops the run if it keeps coming"""


class Lost(ServiceDown):
    """iPhone Mirroring lost the iPhone mid-run ("Connection Interrupted"): open Mirroring again, then the round
    starts over. Before both confirmed nothing traded; after, the trade went through and is counted"""


# ---------- the two phones ----------

def paused_so_far():
    """the seconds the iPhone's process has been paused for the user (its own clock already leaves them out)"""
    try:
        with open(ui.PAUSE_FILE) as f:
            return float(f.read())
    except (OSError, ValueError):
        return 0.0


class Phone:
    def __init__(self, name, android, account, friend):
        self.name, self.account, self.friend, self.android = name, account, friend, android
        env = dict(os.environ)
        env.pop("POGO_PHONE", None)
        if android:
            env["POGO_PHONE"] = "android"
        self.proc = subprocess.Popen([sys.executable, os.path.join(HERE, "phone.py"), name], env=env, text=True,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.texts, self.path, self.screen = [], None, "?"
        self.live = False  # in a trade: from here an "expired" box means start the trade over
        self.stale = False  # a pause changed the screen under a tap: nothing more is sent until the next look
        self.fresh = False  # nothing tapped, typed or keyed since the last look
        self.landed = None  # when this phone's last result screen showed
        self.cooled = False  # a "Trade cooldown" box was kept as a capture this run
        self.ran = None  # the search this run last put on. A long one left from before can look like another in the bar

    def call(self, **req):
        if req["op"] != "look":
            self.fresh = False
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise Stop(f"{self.name}: its phone process ended")
        out = json.loads(line)
        if "error" in out:
            raise Stop(f"{self.name}: {out['error']}")
        return out

    def send(self, **req):
        if not self.stale:
            self.stale = "stale" in self.call(**req)

    def trace(self, what):
        """trace.txt in the run folder: each look and tap to the 1/100 s, for timing a run (a look's capture is
        taken when it's sent, before its OCR)"""
        if base.RUN_DIR:
            os.makedirs(base.RUN_DIR, exist_ok=True)
            with open(os.path.join(base.RUN_DIR, "trace.txt"), "a") as f:
                f.write(f"{time.time():.2f} {self.name} {what}\n")

    def look(self):
        t0 = time.time()
        out = self.call(op="look")
        self.stale = False
        self.texts = [tuple(t) for t in out["texts"]]
        self.path = out["path"]
        self.screen = classify(self.texts, self.path)
        self.fresh = True
        self.trace(f"look {self.screen} sent {t0:.2f} cap {out.get('cap')} ocr {out.get('ocr')}")
        if self.screen == "mirroring":
            self.keep("mirroring")
            raise Lost(f"{self.name}: iPhone Mirroring lost the iPhone: {self.summary()}")
        if self.live and self.screen == "expired":
            self.live = False
            self.expired()
        return self.screen

    def now(self):
        """the screen: the last look's, when nothing was sent to the phone since. Only where the look just before
        is known to be of a settled screen (a Pixel look takes ~1.8 s in a run, an iPhone one ~0.8 s)"""
        return self.screen if self.fresh else self.look()

    def tap(self, fx, fy, fuzz=0.008):
        self.trace(f"tap {fx:.3f} {fy:.3f}")
        self.send(op="tap", fx=fx + random.uniform(-fuzz, fuzz), fy=fy + random.uniform(-fuzz / 2, fuzz / 2))
        time.sleep(random.uniform(0.15, 0.3))

    def tap_text(self, t, dy=0.0):
        x, y, w, h, _ = t
        self.tap(x + w / 2, y + h / 2 + dy, fuzz=min(0.008, w / 4))

    def type(self, text):
        self.send(op="type", text=text)

    def key(self, name):
        self.send(op="key", name=name)

    def wait(self, *screens, timeout=10):
        end = time.time() + timeout
        grace = end + 30  # a blank loading screen (the server is slow) holds the timeout off, this long at most
        held = paused_so_far()
        while True:
            if self.look() in screens:
                return self.screen
            now = paused_so_far()  # the iPhone paused for the user: either phone may be waiting on it, and neither timed out
            end, grace, held = end + max(0.0, now - held), grace + max(0.0, now - held), now
            if self.screen in ("expired", "range"):
                self.expired()
            if time.time() > end and not (self.screen == "blank" and time.time() < grace):
                raise Stop(f"{self.name}: wanted {'/'.join(screens)}, screen is {self.screen}: {self.summary()}")
            time.sleep(0.3)

    def expired(self):
        if self.screen == "range":
            raise OutOfRange(f"{self.name}: {self.friend} is out of range for trading")
        if self.find(lambda t: "UNAVAILABLE" in ui.up(t) or "ERROR FETCHING" in ui.up(t)):
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
        return ui.summary(self.texts)

    def keep(self, tag):
        if self.path and os.path.exists(self.path):
            os.makedirs(base.RUN_DIR, exist_ok=True)
            shutil.copy(self.path, os.path.join(base.RUN_DIR, f"{time.strftime('%H%M%S')}-{self.name}-{tag}.png"))

    def close(self):
        """the run's end: lock the Pixel or quit iPhone Mirroring, then end the phone's process"""
        try:
            self.call(op="close")
        except Exception as e:
            log(f"{self.name}: couldn't close the phone: {e}")
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def both(fn, *argsets):
    """fn on both phones at once (each phone has its own process, so neither waits on the other). Waits for both,
    then raises the worst error: the trading service down, then an expired trade, then any other"""
    with ThreadPoolExecutor(len(argsets)) as ex:
        futs = [ex.submit(fn, *a) for a in argsets]
    out, errs = [], []
    for f in futs:
        try:
            out.append(f.result())
        except BaseException as e:
            out.append(None)
            errs.append(e)
    for kind in (ServiceDown, Expired, BaseException):
        for e in errs:
            if isinstance(e, kind):
                raise e
    return out


# ---------- reading screens ----------

def classify(texts, path):
    raw = [ui.up(t) for t in texts]
    words = {ui.norm(t[4]) for t in texts}
    joined = " ".join(raw)
    if any(w in joined for w in TROUBLE):
        return "mirroring"  # iPhone Mirroring's own screen: it can't reach the iPhone (never on the Pixel)
    if popups.manage_favorite(texts):
        return "manage"  # the Manage Favorite Search box: a shortcut tap that landed as a long press
    if popups.trade_box(texts) == "range":
        return "range"  # "... is out of range for trading": OK
    if "EXIT POK" in joined:
        return "exit"  # Android: "Do you want to exit Pokémon GO?"
    if popups.trade_box(texts):
        return "expired"  # a trade left open too long, the other side left, or the server lost it: OK, start over
    for name, test in (("leave", pages.trade_leave), ("warning", pages.trade_warning), ("confirm", pages.trade_confirm),
                       ("sortmenu", pages.trade_sortmenu), ("waiting", pages.trade_waiting), ("lobby", pages.trade_lobby),
                       ("picker", pages.trade_picker), ("select", pages.trade_select), ("detail", pages.trade_detail),
                       ("result", pages.trade_result)):
        if test(texts):
            return name  # (pages.py has each one, so every script can leave it the way this one does)
    if "SEND GIFT" in words and "LOCAL" in words:
        return "friend"
    if pages.trade_gift(texts):
        return "gift"
    if "ADD FRIEND" in words or "INVITE" in words and "FRIENDS" in words:
        return "friends"
    if "ME" in words and "FRIENDS" in words:
        return "profile"
    if {"TAGS", "EGGS"} <= words:
        return "storage"  # the storage's list or tags tab, left open by another skill: its X closes it (the iPhone has no Back)
    if main_menu(texts):
        return "mainmenu"  # the Poké Ball's menu: POKÉDEX, POKÉMON, SHOP, ITEMS
    if len(texts) <= 12 and pokeball(path):
        return "map"
    if all(t[1] < 0.08 for t in texts):
        return "blank"  # only the status bar: the game is loading
    return "unknown"


confirm_label = pages.confirm_label


def friend_name(p):
    """the name at the top left of a friend page"""
    top = [t for t in p.texts if t[1] < 0.16 and t[0] < 0.2 and re.fullmatch(r"[A-Za-z0-9]{3,}", t[4].strip())]
    return top[0][4].strip() if top else None


def label(p, name):
    hits = p.find(lambda t: ui.norm(t[4]) == name)
    return hits[0] if hits else None


# ---------- getting to the friend page ----------

def to_friend(p, ours=False):
    """ours: this run's own round failed, so a half-made trade is left too (nothing is ever confirmed on the way out)"""
    p.live = False
    unknown, backs, empty = 0, 0, 0
    for i in range(40):  # room for a few Backs out of popups
        s = p.now() if i == 0 else p.look()
        unknown = unknown + 1 if s == "unknown" else 0
        if s == "friend":
            name = friend_name(p)
            if name and name.lower() == p.friend.lower():
                return
            log(f"{p.name}: on {name}'s page, not {p.friend}'s: closing it")
            p.tap(*X_BUTTON)
        elif s in ("exit", "expired", "range"):
            button = label(p, "CANCEL" if s == "exit" else "OK")
            if not button and s != "exit" and (at := popups.trade_ok(p.texts)):  # (OCR can miss the iPhone's green OK)
                p.tap(*at)
                time.sleep(1)
                continue
            if not button:
                raise Stop(f"{p.name}: {s} dialog without its button: {p.summary()}")
            p.tap_text(button)
            if not ours and p.find(lambda t: "UNAVAILABLE" in ui.up(t)):
                raise ServiceDown(f"{p.name}: the trading service is down")
        elif s == "leave":
            if yes := label(p, "YES"):  # (not read yet: the next look tries again)
                p.tap_text(yes)
        elif s == "manage":
            p.tap(*popups.MANAGE_X)
        elif s in ("gift", "result", "mainmenu", "detail", "storage"):
            p.tap(*X_BUTTON)
        elif s == "map":
            p.tap(0.13, 0.91)
        elif s in ("profile", "friends"):
            # a typed search hides ADD FRIEND, so a searched friend list reads as "profile": tap the row if it's there
            row = p.find(lambda t: t[4].strip().lower() == p.friend.lower() and t[0] > 0.2 and t[1] > 0.25)
            bar = p.find(lambda t: t[4].strip().lower() == p.friend.lower() and t[1] <= 0.25)
            if row:
                p.tap_text(row[0], dy=0.01)
            elif bar:
                # the name is in the search bar but no row came up (the game kept a search typed before the list
                # loaded, and it stays empty): clear it with the bar's X, then the next look types it again
                empty += 1
                if empty == 1:  # typed too fast for the game? An A and a delete make it run the search again
                    log(f"{p.name}: the search for {p.friend} shows nobody: an A and a delete")
                    p.tap_text(bar[0])
                    time.sleep(1.2)
                    p.call(op="nudge", q=p.friend)
                    p.key("return")
                elif empty >= 3:
                    x = p.find(lambda t: ui.norm(t[4]) == "X" and t[0] > 0.6 and abs(t[1] - bar[0][1]) < 0.03)
                    if x:
                        p.tap_text(x[0])
                    else:
                        p.tap(0.87, bar[0][1] + bar[0][3] / 2)
                    log(f"{p.name}: the search for {p.friend} came up empty: cleared it")
                    empty = 0
            elif s == "profile":
                if friends := label(p, "FRIENDS"):  # (not read yet: the next look tries again)
                    p.tap_text(friends)
            else:
                search = label(p, "SEARCH")
                if not search:
                    raise Stop(f"{p.name}: friend list without SEARCH: {p.summary()}")
                p.tap_text(search, dy=-0.035)
                time.sleep(1.2)
                p.type(p.friend)
                p.key("return")
        elif s == "sortmenu":
            if recent := label(p, "RECENT"):  # closes it (sort_recent fixes the order later). Not read: look again
                p.tap_text(recent)
        elif s == "picker":
            p.tap(*X_BUTTON)  # back to the trade's lobby
        elif s in ("lobby", "waiting"):
            p.tap(0.09, 0.115)  # the exit door, top left: leave the trade
        elif ours and s == "warning":
            p.tap_text(label(p, "NO") or label(p, "YES"))  # (YES only leads to the confirm screen, the next look backs out)
        elif ours and s == "confirm":
            t = confirm_label(p.texts)
            if t and ui.norm(t[4]) == "CANCEL":
                p.tap_text(t)  # takes back a CONFIRM that landed
            else:
                # the exit door, top left: leave the trade. (Change Pokémon went back to the list, and the list's X
                # back to this screen while the pick stood: the two went round for minutes)
                p.tap(0.09, 0.115)
        elif ours and s == "select":
            p.tap(*X_BUTTON)
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


def tap_local(p):
    """LOCAL TRADE on this phone, as soon as it's on the friend page. Done once the phone has left the page. Too soon
    after the last trade, the game keeps it on the page with a message: tap again"""
    restarted, reloaded, waited = False, False, False
    for attempt in range(TAPS + 1):
        # (always a new look first: a LOCAL tap on the very look that first showed the page, right after the result
        # screen's X, often didn't take, and then no tap took for ~30 s. Old runs: 69 taps a look later, none lost)
        s = p.wait("friend", "waiting", *IN_TRADE, "expired", "range", timeout=8)  # (a banner can cover it for a moment)
        if s == "range":
            p.expired()  # the round starts over: its to_friend taps the OK
        if s == "expired":  # the box from an old trade can come up late, on the friend page
            to_friend(p)
            continue
        if s != "friend":
            return
        t = label(p, "LOCAL")
        if attempt == TAPS or not t:
            raise Stop(f"{p.name}: LOCAL TRADE didn't open: {p.summary()}")
        if attempt and not reloaded:
            log(f"{p.name}: still on the friend page after LOCAL TRADE, tap {attempt + 1}: {p.summary()}")
            if attempt == 1:
                p.keep("local")
        if attempt == 2 and p.android and not restarted and not waited:
            # two taps that did nothing, no cooldown box: the game itself is stuck. A game that had run for hours
            # (2026-11-07) ignored LOCAL taps for 20-107 s after most trades; after a restart 16 in a row took
            # first time, Pixel locks in between too. A restart takes less time than waiting it out
            log(f"{p.name}: LOCAL TRADE taps do nothing: restarting the game")
            p.keep("stuck")
            restarted = reloaded = True
            reload(p)
            to_friend(p)
            continue
        reloaded = False
        since = f", {time.time() - p.landed:.1f} s after its result screen" if p.landed else ""
        p.tap_text(t, dy=-0.035)  # the round icon above the label
        log(f"{p.name}: LOCAL TRADE tapped{since}")
        # a tap that takes leaves the page within ~2-3 s; one that didn't take is tapped again after 5 s, then
        # every 10 s.
        # A "Trade cooldown: 0:xx" box in the middle says how long: wait just that, then tap at once
        end = time.time() + (5 if attempt == 0 else 10)
        while time.time() < end:
            time.sleep(0.4)
            sent = time.time()  # (a look's capture is taken when it's sent)
            p.look()
            left = cooldown(p)  # (first: the box may hide what makes the page read as the friend page)
            if left is None and p.screen != "friend":
                break
            if left is not None:
                waited = True
                if not p.cooled:
                    p.cooled = True
                    p.keep("cooldown")
                log(f"{p.name}: trade cooldown, {left} s: tapping LOCAL TRADE again once it's over")
                time.sleep(max(0.0, sent + left + 0.5 - time.time()))
                break


def cooldown(p):
    """the seconds the "Trade cooldown: 0:xx" box in the middle of the friend page says are left, or None when it
    isn't there. A box with no time read waits 3 s"""
    boxes = p.find(lambda t: "COOLDOWN" in ui.up(t) and 0.25 < t[1] < 0.75)
    if not boxes:
        return None
    y = boxes[0][1]
    for t in sorted(p.find(lambda t: abs(t[1] - y) < 0.06), key=lambda t: abs(t[1] - y)):
        m = re.search(r"(\d{1,2})\s*[:.]\s*(\d{2})\b", t[4])
        if m:
            return int(m.group(1)) * 60 + int(m.group(2))
    return 3


def open_trade(phones):
    """LOCAL TRADE on both. The first one waits ("Waiting for ... to be available") until the second one taps too"""
    both(tap_local, *[(p,) for p in phones])
    try:
        both(lambda p: p.wait("picker", "lobby", "sortmenu", timeout=20), *[(p,) for p in phones])
    except Stop as e:
        if isinstance(e, Expired) or not any([p.look() in ("waiting", "expired") for p in phones]):
            raise
        # the server never joined the two: one waits for the other, or has "Trading service unavailable" up
        raise ServiceDown("the trading service didn't join the two phones")
    both(to_picker, *[(p,) for p in phones])


def to_picker(p):
    for _ in range(6):
        s = p.now()
        if s == "picker":
            return
        if s == "sortmenu":
            if recent := label(p, "RECENT"):  # closes it (sort_recent fixes the order later). Not read: look again
                p.tap_text(recent)
        elif s == "lobby":
            p.tap(0.5, 0.932)  # the Pokémon button at the bottom
        else:
            break
        time.sleep(1.5)
    raise Stop(f"{p.name}: couldn't get back to the Pokémon list: {p.summary()}")


def specials_left(p):
    for t in p.texts:
        m = re.search(r"SPECIAL TRADES REMAINING\W*(\d+)", ui.up(t))
        if m:
            return int(m.group(1))
    return None


# ---------- the picker ----------

def open_panel(p):
    """the search panel with the saved shortcuts. Android: the keyboard comes up over them and is put away"""
    for attempt in range(5):
        if not label(p, "FAVORITE"):
            p.tap(0.5, 0.18)
            time.sleep(1.2)
            p.look()
        keyboard = p.find(lambda t: ui.up(t) in ("?123", "OK") and t[1] > 0.5)
        if keyboard and p.name == "android":
            p.key("back")  # Android: hides the keyboard only, the panel stays
            time.sleep(1.0)
            p.look()
        if label(p, "FAVORITE") and shortcut(p, SAVED[NEAR]) and shortcut(p, SAVED[FAR]):
            return
        if label(p, "FAVORITE"):  # the panel is up, a shortcut isn't read: a banner ("... has connected!") can
            time.sleep(1.0)       # cover it for a few seconds. (This used to go round on the same look)
            p.look()
            if shortcut(p, SAVED[NEAR]) and shortcut(p, SAVED[FAR]):
                return
    p.keep("panel")
    raise Stop(f"{p.name}: the search panel with the saved shortcuts didn't show: {p.summary()}")


def shortcut(p, name):
    hits = p.find(lambda t: t[4].strip().lower() == name.lower())
    return hits[0] if hits else None


def long_pressed(p, name):
    """the shortcut tap landed as a long press: the Manage Favorite Search box is up and the panel stays open.
    Close it and tap the shortcut again. True when it did"""
    if not p.find(lambda t: "MANAGE FAVORITE" in ui.up(t)):
        return False
    log(f"{p.name}: the shortcut tap was a long press: tapping again")
    p.tap(*popups.MANAGE_X)
    time.sleep(1)
    p.look()
    if not (b := shortcut(p, name)):
        raise Stop(f"{p.name}: the {name} shortcut isn't showing after closing Manage Favorite Search: {p.summary()}")
    p.tap_text(b, dy=-0.055)
    return True


def bar(p):
    for t in p.texts:
        s = re.sub(r"\s", "", t[4]).lower()
        if t[1] < 0.24 and ("distance" in s or "candy" in s):  # ('conntcandy': OCR garbles the bar's letters too)
            return s
    return None


def results(p):
    for t in p.texts:
        m = re.search(r"\((\d[\d,]*)\)", t[4])
        if m and t[1] < 0.14:
            return int(m.group(1).replace(",", ""))
    return None


def same_l(s):
    """OCR mixes up l, i, I, 1 and | in the bar ('xix' for 'xlx'): the searches differ elsewhere"""
    return re.sub(r"[il1|]", "l", s.lower())


def in_bar(p, q):
    """the bar shows exactly this search. OCR can miss a '-' (the piles still differ without: 'distance0100',
    'distance100'), and reads a '&' after a digit as an 8 or a 0 as an o. A long search doesn't fit in the bar: the
    Pixel shows its first ~30 characters, the iPhone its last. Either counts once it's past where they all differ.
    A worse read still counts when it's clearly closest to q of this phone's searches (near_bar)"""
    got, want = same_l(bar(p) or "").replace("-", ""), same_l(q).replace("-", "").lstrip("#")  # (a '#' can read as a 9)
    if 0 < got.find(want[:3]) <= 2:
        got = got[got.find(want[:3]):]  # (the magnifier can read as a letter or two in front)
    for g in (got, got[1:]):
        if amp_as_8(g, want) == want:
            return True
        if len(g) >= 22 and any(amp_as_8(g, w) == w for w in (want[:len(g)], want[-len(g):])):
            return True
    return near_bar(p, q)


def pile(s):
    """which distance a search or a bar read is, by where the '-' sits after 'distance': NEAR ('0-100'), FAR
    ('100-'), or None (no '-' read, or 'distance' cut off)"""
    m = re.search(r"ance(.{0,5})", s) or re.search(r"^nce(.{0,5})", s) or re.search(r"^ce(.{0,5})", s)
    if not m or "-" not in m.group(1):
        return None
    return {1: NEAR, 3: FAR}.get(m.group(1).index("-"))


def edits(a, b):
    """how many letters added, dropped or changed turn a into b"""
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (x != y))
    return row[-1]


def near_bar(p, q):
    """a bar the OCR garbled ('giv,xl&distanceo-1i0&conntcandy' for the Pixel's giv,xlx&distance0-100&countcandy0-2499)
    still shows q when the '-' puts it in q's pile and, of this phone's searches in that pile, q is the closest by 2+
    edits. Keeps a search already on (from the last run, or a Return the OCR misread) from being cleared and typed
    again"""
    got = same_l(bar(p) or "")
    if not got or pile(got) is None or pile(same_l(q)) != pile(got):
        return False
    col = 0 if p.name == "ios" else 1
    def far(s):
        w = same_l(s)
        best = edits(amp_as_8(got, w), w)  # the whole search fits
        for k in range(max(1, len(got) - 2), min(len(w), len(got) + 2) + 1):
            part = w[-k:] if col == 0 else w[:k]  # the iPhone shows a long search's end, the Pixel its start
            best = min(best, edits(amp_as_8(got, part), part))
        return best
    others = {plan[col] for plan in PLANS} - {q}
    others = [far(s) for s in others if pile(same_l(s)) == pile(got)]
    d = far(q)
    return d <= max(3, len(got) // 8) and all(o >= d + 2 for o in others)


def shown(p, q):
    """the picker shows q's results: -> how many, 0 too (None: not yet)"""
    if p.screen == "picker" and not label(p, "FAVORITE") and in_bar(p, q):
        return results(p)
    return None


def pick_pile(p, q):
    """tap the saved search and check the bar shows exactly it. -> how many it found"""
    name = SAVED[q]
    if not (b := shortcut(p, name)):
        raise Stop(f"{p.name}: the {name} shortcut isn't showing: {p.summary()}")
    p.tap_text(b, dy=-0.055)  # the round button above the label
    for _ in range(12):
        time.sleep(0.4)
        p.look()
        if long_pressed(p, name):
            continue
        n = shown(p, q)  # the panel closed and the search ran
        if n is not None:
            return n
    p.keep("search")
    raise Stop(f"{p.name}: the search bar doesn't show {q}: {bar(p)!r}, {p.summary()}")


def type_search(p, q):
    """a search that isn't saved: empty the bar, type it, Return. -> how many it found"""
    for attempt in range(3):
        p.look()
        if not label(p, "FAVORITE"):
            p.tap(0.5, 0.18)  # the bar: opens the panel
            time.sleep(1.2)
            p.look()
        box = ui.search_box(p.texts)
        if box and ui.search_text(box):
            p.tap(0.905, 0.183, fuzz=0.004)  # the (x) at the bar's right end: empties it
            time.sleep(1.3)
            p.look()
            if not label(p, "FAVORITE"):
                p.tap(0.5, 0.18)  # the (x) closed the panel too: open it again
                time.sleep(1.2)
                p.look()
        if not label(p, "FAVORITE"):
            log(f"{p.name}: the search panel didn't open: again")
            continue
        if not p.call(op="search", q=q)["ok"]:
            log(f"{p.name}: the typed search came out wrong: again")
            continue
        p.key("return")
        for _ in range(12):
            time.sleep(0.4)
            p.look()
            n = shown(p, q)
            if n is not None:
                return n
        log(f"{p.name}: the bar doesn't show {q} after Return: {bar(p)!r}")
    p.keep("search")
    raise Stop(f"{p.name}: couldn't type the search {q}: {bar(p)!r}, {p.summary()}")


def blank_list(p, n):
    """the search says n: is the list blank? (0, or a count and no tiles once they've had a moment to show)"""
    if n == 0:
        return True
    for _ in range(4):
        if ui.tile_cps(p.texts):
            return False
        time.sleep(0.4)
        p.look()
    return True


def rerun_empty(p, q):
    """q came back blank: an A and a delete make sure the game really ran it (a search read empty is never run again)
    -> how many it found"""
    log(f"{p.name}: {q} shows nothing: an A and a delete to make sure")
    if p.call(op="reopen", q=q)["ok"]:
        p.key("return")
        for _ in range(12):
            time.sleep(0.4)
            p.look()
            n = shown(p, q)
            if n is not None:
                return n
    return type_search(p, q)


def search_for(p, q):
    """q's results in the picker, its saved shortcut or typed. The last trade's search stays on in the list: then
    nothing to run again. One left from before this run is run again: its end can match q while its tag doesn't (a
    Thursday search's end on a Friday). -> how many it found"""
    p.now()
    n = shown(p, q) if p.ran == q else None
    fresh = n is None
    if n is None and q in SAVED:
        open_panel(p)
        n = pick_pile(p, q)
    elif n is None:
        n = type_search(p, q)
    if fresh and blank_list(p, n):
        n = rerun_empty(p, q)
    p.ran = q
    log(f"{p.name}: {q} ({n})")
    return n


RECENT_ICON = os.path.join(HERE, "recent_icon.png")  # the sort button's clock and down arrow, green on teal


def sorted_recent(path):
    """the sort button already shows Recent (the clock) with the arrow down: newest first, nothing to set"""
    return (ui.icon_score(path, RECENT_ICON, (325, 805)) or 0) >= 0.6 and ui.sort_arrow(path, right_most=True) == "down"


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
        for _ in range(4):  # no arrow read: the menu can still be fading out. Look again before tapping again
            time.sleep(0.5)
            p.look()
            way = ui.sort_arrow(p.path, right_most=True)
            if way:
                break
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
    for attempt in range(3):  # a tap on a list that's still settling can do nothing: tap again
        try:
            t = tile(p, i)
        except Stop:  # (the look was made before the tiles showed)
            time.sleep(0.4)
            p.look()
            t = tile(p, i)
        p.tap_text(t, dy=0.06)
        try:
            p.wait("select", timeout=4 if attempt < 2 else 8)
            break
        except Expired:
            raise
        except Stop:
            if attempt == 2 or p.screen != "picker":
                raise
            log(f"{p.name}: the tile tap didn't open it: again")
    name = next((t[4] for t in sorted(p.texts, key=lambda t: t[1]) if t[1] > 0.09 and t[0] < 0.3), "?")
    cp = next((ui.up(t) for t in p.texts if re.search(r"CP\s*\d+\s*>", ui.up(t))), "")
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
        if s == "confirm" or s == "lobby" and any(re.search(r"CP\s*\d+\s*-\s*\d+", ui.up(t)) for t in p.texts):
            return name.strip()  # (lobby: picked, waiting for the other side to pick)
    raise Stop(f"{p.name}: NEXT didn't lead to the confirm screen: {p.summary()}")


def warning(p):
    """'Are you sure you want to trade this Pokémon?' plus the reasons: YES only if every reason is a known one"""
    top = next(t[1] for t in p.texts if "ARE YOU SURE" in ui.up(t))
    yes = label(p, "YES")
    if not yes:
        raise Stop(f"{p.name}: trade warning without YES: {p.summary()}")
    lines = [re.sub(r"^[^A-Z]+", "", ui.up(t)) for t in p.texts if top < t[1] < yes[1] - 0.01]
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
    if not re.fullmatch(r"(?:\S\s*)?%d" % COST, text) or re.fullmatch(r"\d{2,}", text) and text not in COST_READS:
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
    """the catch spots' distance. OCR can swap ',' and '.' ('4,125.4' as '4.125.4'), so the last group says which it
    is: 1 or 2 digits are the decimals, 3 are thousands"""
    for t in p.texts:
        m = re.search(r"(\d+(?:[.,]\d+)*)\s*km", t[4], re.I)
        if m and 0.48 < t[1] < 0.6:
            *whole, last = re.split(r"[.,]", m.group(1))
            return float("".join(whole) + "." + last) if whole and len(last) < 3 else float("".join(whole) + last)
    return None


def check_confirm(p):
    """three tries at a clean read: a regular cost and the catch spots far enough apart"""
    why = ""
    p.wait("confirm", timeout=20)  # the first to pick waits in the lobby for the other
    for k in range(5):
        if (p.screen if k == 0 else p.look()) == "confirm":
            ok, why = cost_ok(p)
            d = km(p)
            if ok and d is not None:
                candy = next((ui.up(t) for t in p.texts if re.fullmatch(r"\+\d", ui.up(t))), "?")
                return d, candy
            why += f", {d} km"
        time.sleep(0.3)
    p.keep("confirm")
    raise Stop(f"{p.name}: won't confirm: {why}")


def confirm(p):
    """CONFIRM once. Once it lands the button reads CANCEL in the same spot: only tap again while it says CONFIRM"""
    for attempt in range(6):
        if p.screen == "detail":
            # the tap landed on the Pokémon's own card: its info opened over the confirm screen. Close it
            log(f"{p.name}: CONFIRM opened the Pokémon's info: closing it")
            p.tap(*X_BUTTON)
            p.wait("confirm", timeout=5)
        t = confirm_label(p.texts) if p.screen == "confirm" else None
        if not t:
            return  # the trade animation has started
        if ui.norm(t[4]) == "CANCEL":
            return
        if attempt:
            log(f"{p.name}: CONFIRM didn't land, again")
        p.tap_text(t)
        end = time.time() + 2.5  # a tap that took reads CANCEL within a look or two. (Six looks here kept a lost
        while time.time() < end:  # iPhone tap waiting ~9 s)
            time.sleep(0.3)
            if p.look() == "detail":
                break
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

def pick(p, q, specials):
    """q's results on, sorted newest first, the top one picked, all without waiting for the other phone.
    -> (how many q found, the name picked, None when it found none)"""
    n = search_for(p, q)
    if not n:
        return n, None
    p.now()
    if p.name not in specials.setdefault("sorted", []):  # once a run: the sort stays put between trades
        if sorted_recent(p.path):
            log(f"{p.name}: already sorted Recent, newest first")
        else:
            sort_recent(p)
        specials["sorted"].append(p.name)
    elif ui.sort_arrow(p.path, right_most=True) != "down":
        sort_recent(p)
    return n, choose(p)


def plan(phones, specials):
    """the first of PLANS with Pokémon left on both phones, its top ones picked -> (iPhone search, Android search, why,
    [iPhone's, Android's]). A phone that picked while the other's search came up empty puts its pick back, and the next
    plan goes on. A count can only go down (a trade takes one off a pile, and the candy it gives can push a species off a
    needy search), so a search read empty is never run again: left remembers them, {phone: {search: how many}}"""
    left = specials.setdefault("left", {p.name: {} for p in phones})
    for qi, qa, why in PLANS:
        qs = (qi, qa)
        if any(left[p.name].get(q, 1) < 1 for p, q in zip(phones, qs)):
            continue
        if any(q not in left[p.name] for p, q in zip(phones, qs)):
            ns = both(search_for, *[(p, q) for p, q in zip(phones, qs)])
            for p, q, n in zip(phones, qs, ns):
                left[p.name][q] = n
            if not all(ns):
                continue
        out = both(pick, *[(p, q, specials) for p, q in zip(phones, qs)])
        for p, q, (n, _) in zip(phones, qs, out):
            left[p.name][q] = n
        names = [name for _, name in out]
        if all(names):
            return qi, qa, why, names
        for p, name in zip(phones, names):
            if name:
                log(f"{p.name}: the other phone has none of this pair: putting {name} back")
                to_picker(p)
    return None


def trade_once(ios, android, specials, fresh=False, rehearse=False):
    """one trade. specials: what the run remembers between trades (special trades left, phones already sorted).
    fresh: the last round failed, so both phones back out to the friend page first. rehearse: everything up to the
    confirm screen's reads, then no CONFIRM (-> "rehearsed"): the next round backs out (fresh)"""
    phones = (ios, android)
    if fresh:
        both(lambda p: to_friend(p, ours=True), *[(p,) for p in phones])
        open_trade(phones)
    else:
        screens = both(lambda p: p.look(), *[(p,) for p in phones])  # (each look takes a while: at once)
        for _ in range(6):
            # a look caught between two screens (unknown, blank) says nothing: look again. (2026-11-08: the Pixel
            # read "unknown" on its way into the picker, got backed out, and the iPhone's wait expired)
            if not any(s in ("unknown", "blank") for s in screens):
                break
            time.sleep(0.5)
            screens = both(lambda p: p.look() if p.screen in ("unknown", "blank") else p.screen,
                           *[(p,) for p in phones])
        if all(s in IN_TRADE for s in screens):
            both(to_picker, *[(p,) for p in phones])  # both still in a trade from before: carry on in it
        elif all(s in IN_TRADE or s == "waiting" for s in screens):
            open_trade(phones)  # finish() tapped LOCAL TRADE on both: they're joining
        else:
            # waiting already: LOCAL TRADE on the other phone lets it in
            both(lambda p: p.screen == "waiting" or to_friend(p), *[(p,) for p in phones])
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
    picked = plan(phones, specials)
    if not picked:
        return None  # both phones are left in the picker: nothing picked, nothing to undo
    qi, qa, why, got = picked
    log(f"pair: {why}")
    far = FAR in (qi.replace(NEED, ""), qa.replace(NEED, ""))  # 0-100km with 0-100km: any distance goes
    for skip in range(SKIPS + 1):
        reads = both(check_confirm, *[(p,) for p in phones])
        for _ in range(2):  # a read can drop the decimal point (3,853.3 as 38533.0): read both again
            if abs(reads[0][0] - reads[1][0]) <= 1:
                break
            log(f"the phones read different distances: {reads}: reading again")
            time.sleep(0.5)
            reads = both(check_confirm, *[(p,) for p in phones])
        a, b = sorted(r[0] for r in reads)
        if b > EARTH_KM and abs(b / 10 - a) <= 1:  # no two spots on Earth are that far apart: the point was dropped
            reads = [(a, r[1]) for r in reads]
        d = reads[0][0]
        if abs(reads[0][0] - reads[1][0]) > 1:
            raise Stop(f"the phones read different distances: {reads}")
        if d >= MIN_KM or not far:
            break
        if skip == SKIPS:
            raise Stop(f"still under {MIN_KM} km after skipping {SKIPS} of the Android's: nothing confirmed")
        # too close: the Android puts its pick back and offers its next one instead
        log(f"{got[0]} and {got[1]} were caught only {d} km apart: Android tries its next one")
        android.tap(0.5, 0.932)  # change Pokémon: back to the list, search kept
        android.wait("picker", timeout=10)
        got[1] = choose(android, skip + 1)
    if rehearse:
        log(f"rehearsal: {got[0]} <-> {got[1]}, {d:,.1f} km, read OK: no CONFIRM")
        return "rehearsed"
    def tap_confirm(p):
        try:  # (the reader can miss a letter of CONFIRM on one capture)
            if not (p.fresh and p.screen == "confirm" and confirm_label(p.texts)):
                p.wait("confirm", timeout=4)
        except Expired:
            raise
        except Stop:
            raise Stop(f"{p.name}: left the confirm screen before CONFIRM: {p.summary()}")
        confirm(p)
    both(tap_confirm, *[(p,) for p in phones])  # at once: neither phone waits for the other's tap
    for p in phones:
        p.live = False  # confirmed: an "expired" box from here on comes after the trade, it doesn't undo it
    return got, d, reads[0][1]


def finish(phones, again):
    """each phone on its own: wait out the animation, note its result screen showed, close it, and (again: another
    trade comes next) tap LOCAL TRADE right away"""
    def close(p):
        try:
            if p.wait("result", "expired", timeout=45) == "expired":
                # seen on the Android once, while the iPhone got its Pokémon: the trade went through all the same
                log(f"{p.name}: says the trade expired after both confirmed: the next round clears it")
                return
            p.landed = time.time()
            log(f"{p.name}: result screen showed")
            for _ in range(3):
                p.tap(*X_BUTTON)
                for _ in range(5):
                    time.sleep(0.3)
                    if p.look() != "result":
                        break
                if p.screen != "result":
                    break
            if again:
                to_friend(p)
                tap_local(p)
        except Lost:
            raise
        except Expired as e:  # the trade went through: the next round sorts this phone out
            log(f"{e}: the next round starts from here")
    both(close, *[(p,) for p in phones])


def restart(phones):
    """force-close and open the game on both, then wait until each is past the loading screens (trade.py restart)"""
    for p in phones:
        p.restart()
    for p in phones:
        loaded(p)
    log("both phones restarted")


def reload(p):
    """force-close and open the game on this phone, then wait until it's past the loading screens"""
    t0 = time.time()
    p.restart()
    loaded(p)
    log(f"{p.name}: the game is back after {time.time() - t0:.0f} s")


def loaded(p):
    end = time.time() + 120
    time.sleep(3)  # (the old game can still be on screen for a moment)
    while p.look() in ("unknown", "blank"):  # loading screens and their tips
        if time.time() > end:
            p.keep("restart")
            raise Stop(f"{p.name}: the game didn't load after the restart: {p.summary()}")
        time.sleep(3)


def reconnect(phones):
    """iPhone Mirroring lost the iPhone: open it again, with the game up. The game itself isn't restarted"""
    for p in phones:
        if not p.android:
            p.call(op="reconnect")
            log(f"{p.name}: iPhone Mirroring back, on {p.start()}")


def cmd_look(phones):
    both(lambda p: p.call(op="ready"), *[(p,) for p in phones])  # a run's end locked the Pixel and quit Mirroring
    for p in phones:
        s = p.look()
        print(f"{p.name} ({p.account}): {s}")
        print("   ", p.summary())


def main():
    global COST, COST_READS
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=("run", "look", "restart"))
    ap.add_argument("--limit", type=int, default=PER_RUN)
    ap.add_argument("--rehearse", type=int, default=0,
                    help="N rounds up to the confirm screen, never confirmed (for timing): trades nothing")
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
        friday = friendship_friday()
        if friday:
            set_piles("#2xl", saved=False)
            COST, COST_READS = FRIDAY_COST, FRIDAY_READS
            log("Friendship Friday: only the ones tagged 2XL")
        made, n, specials, expired, fresh = made_today(), 0, {}, 0, False
        rehearsed = 0
        log(f"{made} trades made today so far, {PER_DAY} a day; this run: at most {a.limit}")
        while n < a.limit and (not a.rehearse or rehearsed < a.rehearse):
            if friendship_friday() != friday:
                log("midnight: what can be traded changed. Start the run again")
                break
            if made_today() >= PER_DAY:
                log(f"{PER_DAY} trades today: done for the day")
                break
            try:
                got = trade_once(ios, android, specials, fresh, rehearse=bool(a.rehearse))
            except Expired as e:
                expired += 1
                if expired > 3:
                    raise Stop(f"{e}, {expired} times in a row")
                log(f"{e}: backing out to the friend page, then trying again")
                if isinstance(e, Lost):
                    reconnect(phones)
                fresh = True
                continue
            expired, fresh = 0, False
            if got == "rehearsed":
                rehearsed, fresh = rehearsed + 1, True  # the next round backs both out of this one first
                continue
            if not got:
                log(f"no {'2XL ' if friday else ''}pairs left (the 100+km ones are kept for another day): done")
                break
            set_made(made_today() + 1)  # counted once both have confirmed: a missed result screen never undercounts
            n += 1
            names, d, candy = got
            log(f"trade {made_today()} today: {names[0]} (iPhone) <-> {names[1]} (Android), {d:,.1f} km, {candy} candy")
            try:
                finish(phones, n < a.limit and made_today() < PER_DAY and friendship_friday() == friday)
            except Lost as e:  # both confirmed: the trade went through, only its result screens are left
                log(f"{e}: the trade went through")
                reconnect(phones)
                fresh = True
        if rehearsed:  # the last rehearsal is still on the confirm screen: leave it, nothing confirmed
            both(lambda p: to_friend(p, ours=True), *[(p,) for p in phones])
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
