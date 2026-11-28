#!/usr/bin/env python3
"""Defend a gym under attack: feed a Golden Razz to each Pokémon whose heart turns more black than pink, as fast as
it can, then X back to the gym view to watch every heart again (the user, 2026-11-28).

  python3 gymdefend.py [--for SECONDS] [--no-pixel]          feed on the iPhone, watch the Pixel too
  POGO_PHONE=android python3 gymdefend.py [--for SECONDS]    feed on the Pixel

- Start it with the gym view up on the phone that feeds: it doesn't walk there (home.start() would leave the gym).
  It ends after --for seconds, or after GONE_END seconds with no heart seen (the gym was lost, or left).
  Mirroring or the Pixel stays as it is at the end.
- The gym view is read over and over, only the band with the hearts. Each heart is found by its pink part, and the
  black is counted in the heart-sized box above it: the two parts don't always touch (a heart read 0 % black while
  it was over half black, 2026-11-28). A frame older than STALE seconds is never acted on: an iPhone capture once
  stalled 30 s and the feed came too late.
- A heart at THRESH black or more: a tap just under it, on the side away from its nearest neighbour (a tap under
  Chansey's heart once opened Blissey, who stands in front), then BERRY menu, Golden Razz, the berry, X. The X waits
  X_WAIT after the berry on the iPhone: one tapped while the berry flies is dropped.
- The iPhone never waits for the Mac to be idle here: its taps go in over the user's mouse (the user, 2026-11-28,
  for this script only).
- Feeding the iPhone, it also watches the Pixel (watched only, never tapped: the user feeds there by hand). The two
  phones' hearts update at different times, so a black heart on either one is a feed. A Pixel heart is a late report
  when the iPhone fed that Pokémon less than FED_HOLD s ago, or less than 45 s ago and shows it under 20 % black. A
  Pixel heart that goes black, then full within 60 s, was fed by hand there: the iPhone's black heart for it is then
  late for PX_HOLD s.
- The game takes 10 berries per Pokémon per 30 minutes from each trainer, counted from the first feed. Each feed is
  saved by the Pokémon's page name in runs/gymdefend-feeds-<phone>.json, so a restart remembers them, and a Pokémon
  with 10 in its window isn't tapped again until the window ends. Its count goes in the log with each feed.
- THRESH, FED_HOLD, PX_HOLD, X_WAIT and COOLDOWN can change while it runs: put them in runs/gymdefend-settings.json
  (e.g. {"THRESH": 0.5}). It reads the file again when it changes.
Log: runs/<time>-gymdefend-<phone>/log.txt, with a picture of each frame that started a feed.
"""
import argparse, json, os, sys, threading, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui, base, session
from base import log
import gymfeed as g
from PIL import Image

PHONE = "android" if ui.ANDROID else "iphone"
RUNS = os.path.join(HERE, "runs")
FEEDS = os.path.join(RUNS, f"gymdefend-feeds-{PHONE}.json")
SETTINGS = os.path.join(RUNS, "gymdefend-settings.json")
GOLDEN = (0.19, 0.867) if ui.ANDROID else (0.20, 0.869)  # Golden Razz in the BERRIES menu (both read 2026-11-28)
BAND = (0.3, 0.75)  # the band of the screen the hearts sit in (fractions of the phone's height, and of a capture)
STALE = 1.5  # seconds: an older frame is never acted on
GONE_END = 120  # seconds with no heart seen: the gym is gone, the run ends
WINDOW, PER_WINDOW = 30 * 60, 10  # the game's berry limit per Pokémon, from its first feed
SPOTS = [(0.04, 0.06), (0.07, 0.08), (0.0, 0.045), (0.05, 0.03)]  # (dx away from the neighbour, dy) under a heart
SET = {"THRESH": 0.42, "FED_HOLD": 8, "PX_HOLD": 45, "X_WAIT": 0.25 if ui.ANDROID else 1.4, "COOLDOWN": 2.5}
_set_seen = [None]


def settings():
    """SET, with runs/gymdefend-settings.json read again when it changed"""
    try:
        m = os.path.getmtime(SETTINGS)
    except OSError:
        return SET
    if m != _set_seen[0]:
        _set_seen[0] = m
        try:
            new = {k: float(v) for k, v in json.load(open(SETTINGS)).items() if k in SET}
            SET.update(new)
            log(f"settings now {SET}")
        except (ValueError, OSError) as e:
            log(f"settings file not read: {e}")
    return SET


# ---------- the berry count per Pokémon ----------

def load_feeds():
    try:
        return {k: list(v) for k, v in json.load(open(FEEDS)).items()}
    except (OSError, ValueError):
        return {}


def window(times, now=None):
    """-> (berries in the window now open, when it ends) from a Pokémon's feed times. A window opens at the first
    feed after the last one ended (the game counts 30 min from the first feed)"""
    now = now or time.time()
    start, n = None, 0
    for t in sorted(times):
        if start is None or t >= start + WINDOW:
            start, n = t, 0
        n += 1
    if start is None or now >= start + WINDOW:
        return 0, None
    return n, start + WINDOW


def note_feed(feeds, name):
    now = time.time()
    feeds[name] = [t for t in feeds.get(name, []) if now - t < 2 * WINDOW] + [now]
    os.makedirs(RUNS, exist_ok=True)
    json.dump(feeds, open(FEEDS, "w"))
    n, end = window(feeds[name])
    return n, end


# ---------- the hearts ----------

def pink(p):
    r, gg, b = p
    return r > 140 and r - gg > 60 and r - b > 40 and b > gg


def dark(p):
    return max(p) < 75 and max(p) - min(p) < 25


def heart_levels(im):
    """a band of the gym view at 406 wide -> [(cx, bottom y, black share)], fractions of the band. Unlike
    gymfeed.hearts (pink and dark in one blob, sized as a whole heart), each heart is found by its pink part alone
    and the black is counted in the heart-sized box above it: the two parts don't always touch"""
    w, h = im.size
    px = im.load()
    pts = {(x, y) for y in range(h) for x in range(w) if pink(px[x, y])}
    out = []
    for blob in ui.blobs(pts):
        if len(blob) < 8:
            continue
        xs = [x for x, _ in blob]
        ys = [y for _, y in blob]
        bw, bot = max(xs) - min(xs) + 1, max(ys)
        if not 12 <= bw <= 60 or bot - min(ys) > 60:
            continue
        top = int(bot - 0.95 * bw)
        if top < 0:
            continue
        dk = pk = 0
        for y in range(top, bot + 1):
            for x in range(max(0, min(xs) - 1), min(w, max(xs) + 2)):
                q = px[x, y]
                if pink(q):
                    pk += 1
                elif dark(q):
                    dk += 1
        if dk + pk < 0.3 * bw * bw:  # not heart-shaped: too little of either colour in its box
            continue
        out.append(((min(xs) + max(xs)) / 2 / w, bot / h, dk / (dk + pk)))
    return sorted(out)


# ---------- the screenshots, each in its own thread ----------

pause = threading.Event()  # set while feeding: frames taken mid-feed would show the feed page


def own_frames(slot):
    """the feeding phone's band, over and over -> slot[0] = (when taken, image, (cy0, cy1))"""
    while True:
        if pause.is_set():
            time.sleep(0.05)
            continue
        t = time.time()
        try:
            if ui.ANDROID:
                got = ui.android.band_shot(*BAND)
                if got is None:
                    continue
                im, span = got
            else:
                p, _ = ui.capture()
                im = Image.open(p).convert("RGB")
                im = im.crop((0, int(BAND[0] * im.height), im.width, int(BAND[1] * im.height)))
                if im.width != 406:
                    im = im.resize((406, round(406 * im.height / im.width)))
                span = BAND
        except Exception as e:  # (a look that fails is only a look missed)
            log(f"  look failed: {type(e).__name__}: {e}")
            time.sleep(0.5)
            continue
        if time.time() - t > STALE:
            log(f"  a look took {time.time() - t:.1f}s")
        if not pause.is_set():
            slot[0] = (t, im, span)
        time.sleep(0.02)


def pixel_frames(slot):
    """the Pixel's band while the iPhone feeds (watched only)"""
    import android
    while True:
        t = time.time()
        try:
            got = android.band_shot(*BAND)
        except Exception:
            got = None
        if got is None:
            time.sleep(0.2)
            continue
        if slot[0] is None or slot[0][0] < t:
            slot[0] = (t, got[0], got[1])


# ---------- one feed ----------

def is_page(v):
    return v[0] == "feed"


def feed(cx, cy, bounds, spots, feeds, names):
    """tap under the heart at (cx, cy) (capture fractions), feed a Golden Razz, X back.
    -> the Pokémon's name, or None when no page opened or it already has its 10"""
    t0 = time.time()
    v = None
    for dx, dy in spots:
        base.click(cx + dx, cy + dy, bounds, counted=False)
        v = base.settle(g.look, is_page, timeout=1.5, gap=0)
        if is_page(v):
            break
        if v[0] != "gymview":
            log(f"  odd screen after the tap: {v[0]}")
            back_out(v[3])
            return None
    if not is_page(v):
        log("  no page opened")
        return None
    _, texts, _, bounds = v
    name = g.page_name(texts) or "?"
    names[round(cx, 2)] = name
    n, end = window(feeds.get(name, []))
    if n >= PER_WINDOW:
        log(f"  {name} has its {n} berries till {time.strftime('%H:%M:%S', time.localtime(end))}: no feed")
        back_out(bounds)
        return None
    # blind from here: menu, Golden Razz, the berry, X. back_out checks the gym view is back
    base.click(*g.BERRY_MENU, bounds, counted=False)
    time.sleep(0.6)
    base.click(*GOLDEN, bounds, counted=False)
    time.sleep(0.45)
    base.click(*g.BERRY, bounds, counted=False)
    time.sleep(settings()["X_WAIT"])
    base.click(*base.X_BUTTON, bounds, counted=False)
    n, end = note_feed(feeds, name)
    log(f"  fed {name} a Golden Razz in {time.time() - t0:.1f}s: {n}/{PER_WINDOW} till "
        f"{time.strftime('%H:%M:%S', time.localtime(end))}")
    back_out(bounds)
    return name


def back_out(bounds):
    """X until the gym view shows again (an X tapped while the berry is eaten can be dropped)"""
    for _ in range(6):
        s, texts, _, bounds = g.look()
        if s == "gymview":
            return True
        if s == "berrymenu":
            base.click(*g.OFF_MENU, bounds, counted=False)
        elif s == "feed":
            base.click(*base.X_BUTTON, bounds, counted=False)
            log("  X again")
        else:
            log(f"  odd screen: {s}, not tapping")
            return False
        time.sleep(0.4)
    return False


# ---------- picking what to feed ----------

class Pixel:
    """what the Pixel's hearts say, while the iPhone feeds: black ones, and the ones fed there by hand"""

    def __init__(self):
        self.black, self.fed = {}, {}  # heart x -> when it was last seen black / seen refilled

    def read(self, hs):
        now, cut = time.time(), settings()["THRESH"]
        for cx, _, d in hs:
            near = [k for k in self.black if abs(k - cx) <= 0.08]
            if d >= cut:
                for k in near:
                    self.black.pop(k)
                self.black[cx] = now
            elif d < 0.2:
                for k in near:
                    if now - self.black.pop(k) < 60:
                        self.fed[cx] = now
                        log(f"  the Pixel fed its heart at x{cx:.2f}: the iPhone's word on it waits")

    def hand_fed(self, cx):
        return any(abs(k - cx) <= 0.08 and time.time() - t < settings()["PX_HOLD"] for k, t in self.fed.items())


def pick(hs, ph, last, px, full):
    """-> ((cx, fy, share), why) of the heart to feed now, or None. hs: the feeding phone's hearts, ph: the Pixel's
    (or None). last: heart x (1 place) -> when it was last fed. full: heart x -> True when its Pokémon has its 10"""
    s, now = settings(), time.time()
    for h in sorted(hs, key=lambda h: -h[2]):
        k = round(h[0], 1)
        if h[2] >= s["THRESH"] and now - last.get(k, 0) >= s["COOLDOWN"] and not px.hand_fed(h[0]) and not full(h[0]):
            return h, f"heart {h[2]:.0%} black"
    for pcx, _, pd in ph or []:
        if pd < s["THRESH"]:
            continue
        m = min(hs, key=lambda h: abs(h[0] - pcx))  # the same spot on both: both views sit alike
        if abs(m[0] - pcx) > 0.08 or full(m[0]):
            continue
        since = now - last.get(round(m[0], 1), 0)
        # just fed and full here: the Pixel's heart is late (it fed Chansey for nothing, 2026-11-28 02:32:55)
        if since >= s["FED_HOLD"] and not (since < 45 and m[2] < 0.2):
            return m, f"Pixel heart x{pcx:.2f} {pd:.0%} black (here {m[2]:.0%})"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--for", dest="secs", type=float, default=None, help="end after this many seconds")
    ap.add_argument("--no-pixel", action="store_true", help="feeding the iPhone: don't watch the Pixel")
    a = ap.parse_args()
    if not ui.ANDROID:  # this gym only: taps go in over whatever the user does on the Mac
        base.user_active = lambda: False
        base.idle_seconds = lambda: 999.0
        base.yield_to_user = lambda *x, **k: None
    os.environ["POGO_NO_RESTART"] = "1"  # (a phone restart now would lose the gym)
    base.new_run_dir(RUNS, suffix="gymdefend-" + PHONE)
    session.ready()
    s, _, _, bounds = g.look()
    log(f"gymdefend on the {PHONE}, starting on: {s}")
    feeds = load_feeds()
    for name, times in feeds.items():
        n, end = window(times)
        if n:
            log(f"  {name}: {n}/{PER_WINDOW} berries till {time.strftime('%H:%M:%S', time.localtime(end))}")
    own, pixel = [None], [None]
    threading.Thread(target=own_frames, args=(own,), daemon=True).start()
    watch_px = not ui.ANDROID and not a.no_pixel
    if watch_px:
        for _ in range(3):  # (3 in a row: a look every ~0.2 s)
            threading.Thread(target=pixel_frames, args=(pixel,), daemon=True).start()
            time.sleep(0.2)
    px, last, tries, names = Pixel(), {}, {}, {}
    seen_own = seen_px = 0
    hs, span, n = [], BAND, 0
    began = heard = time.time()

    def full(cx):
        name = next((nm for x, nm in names.items() if abs(x - cx) <= 0.04), None)
        return name is not None and window(feeds.get(name, []))[0] >= PER_WINDOW

    while True:
        now = time.time()
        if a.secs is not None and now - began >= a.secs:
            log(f"--for {a.secs:.0f}s is up")
            break
        if now - heard >= GONE_END:
            log(f"no heart seen for {GONE_END}s: the gym is gone")
            break
        got, gp = own[0], pixel[0]
        new_own = got is not None and got[0] != seen_own and now - got[0] <= STALE
        new_px = gp is not None and gp[0] != seen_px and now - gp[0] <= STALE
        if not new_own and not new_px:
            time.sleep(0.02)
            continue
        if new_own:
            seen_own, im, span = got
            hs = heart_levels(im)
            n += 1
            if n % 50 == 1:
                log("hearts: " + (", ".join(f"x{cx:.2f} {d:.0%}" for cx, _, d in hs) or "none"))
            if hs:
                heard = now
            elif n % 4 == 0:  # no hearts: maybe left on a feed page
                v = g.look()
                if v[0] in ("feed", "berrymenu"):
                    log(f"  still on {v[0]}: backing out")
                    back_out(v[3])
        ph = None
        if new_px:
            seen_px, pim, _ = gp
            ph = heart_levels(pim)
            px.read(ph)
        if not hs:
            continue
        got_pick = pick(hs, ph, last, px, full)
        if got_pick is None:
            continue
        (cx, fy, d), why = got_pick
        key = round(cx, 1)
        log(f"{why}: feeding x{cx:.2f}")
        im.save(os.path.join(base.RUN_DIR, time.strftime("feed-%H%M%S.png")))
        pause.set()
        others = [o[0] for o in hs if abs(o[0] - cx) > 0.05]
        side = 0 if not others else (1 if cx > min(others, key=lambda o: abs(o - cx)) else -1)
        tries[key] = tries.get(key, 0) + 1 if time.time() - last.get(key, 0) < 15 else 0
        k = tries[key] % len(SPOTS)
        spots = [(side * dx, dy) for dx, dy in SPOTS[k:] + SPOTS[:k]]
        feed(cx, span[0] + fy * (span[1] - span[0]), bounds, spots, feeds, names)
        last[key] = time.time()
        own[0] = None
        hs = []
        pause.clear()
    log("gymdefend done")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("stopped by hand")
