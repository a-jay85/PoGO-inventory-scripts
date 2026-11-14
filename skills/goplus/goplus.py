#!/usr/bin/env python3
"""Connect the GO Plus+: tap its Poké Ball at the top right of the map. Pixel only.

  POGO_PHONE=android caffeinate -dimsu python3 goplus.py [--look]

Which phone and account (the user, 2026-11-10):
- Pixel + CyrillJan: the GO Plus+ is paired with it and always on (while its battery lasts), so a tap connects, every
  time. No time limit.
- Pixel + HashTagAJay: it never connects (the user won't pair it again for that account). The script says so and
  doesn't tap. Switch first: pogo.py account CyrillJan.
- iPhone: a tap through iPhone Mirroring never connects, so the script stops right away.

The ball, read off the screenshot (it sits under the weather and any raid timer, so it's looked for, not tapped blind):
- off: a dull ball, pinkish-grey top, blue bottom, dark navy middle.
- connecting: the same dull ball with a white ring spinning round it (about 4 s on the Pixel).
- on: a bright ball, red top, white bottom, green middle.
Already on: nothing is tapped. A tap on an "on" ball disconnects it at once (no box), so the script never taps one.

It starts from any screen and goes to the map. Then: off -> one tap, and it waits for "on" (CONNECT_TIMEOUT). Not on:
one more tap and wait (a lost tap, or a try that gave up). Still not on: it stops. The ring is too faint over the light
map to read, so it isn't used.
--look reads the ball and says what it is. No taps beyond getting to the map.

The timer (skills/shared/timer.py): once the ball is on (connected, or already on), the next goplus run is set for
AGAIN min later, so it connects again by itself. The wrong account signed in turns the timer off, so it doesn't try
every hour for nothing; the next CyrillJan run that connects (by hand, or after a switch) turns it on again (the user,
2026-11-14). --look and any other stop don't set it (a timed run that stopped tries again 60 min after it ended).
No more timed runs: python3 skills/shared/timer.py off goplus.
Log in runs/<time>-android/log.txt.
"""
import argparse, os, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log, keep_capture
import home, session, timer

FOR = "CyrillJan"  # the one account the GO Plus+ is paired with
AREA = (0.84, 0.05, 1.0, 0.40)  # where the ball can be: the map's right-hand icon column (middle x 0.914), under the
# weather and a raid timer. Wider took in a pink gym ring over the night map's blues (2026-11-12)
AGAIN = 60  # minutes from a connect to the next timed run (the user, 2026-11-14)
CONNECT_TIMEOUT = 15 # seconds from a tap to "on": about 6 s seen (Pixel, 2026-11-10)


def green(p):
    return p[1] > 200 and p[0] < 170 and p[2] < 150 and p[1] - p[0] > 70


def red(p):
    return p[0] > 200 and p[1] < 100 and p[2] < 100


def white(p):
    return min(p) > 235


def navy(p):
    return p[0] < 85 and p[1] < 105 and 80 < p[2] < 145 and p[2] - p[0] > 25


def mauve(p):  # the off ball's top half
    return 110 < p[0] < 175 and 70 < p[1] < 125 and 95 < p[2] < 155 and p[0] - p[1] > 15


def blue(p):  # the off ball's bottom half
    return p[2] > 170 and p[2] - p[0] > 50 and 110 < p[1] < 190


def ball(path):
    """the GO Plus+ ball in AREA -> (state, fx, fy): state "on" or "off", (fx, fy) its middle as fractions.
    None: no ball seen (a popup over it, or not the map).
    A middle pixel counts when the ball's own top colour is just above it and its bottom colour just below: the map has
    greens and navies of its own (the battery icon's green, a Pokémon's eye), never with both of those round them"""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = im.load()
    reach = range(2, max(4, int(0.05 * W)))  # the middle to the halves' colours: up to the ball's radius
    found = {"on": [], "off": []}
    for x in range(int(AREA[0] * W), int(AREA[2] * W) - 1):
        for y in range(int(AREA[1] * H), int(AREA[3] * H)):
            p = px[x, y]
            for state, mid, top, bottom in (("on", green, red, white), ("off", navy, mauve, blue)):
                if mid(p) and any(top(px[x, y - k]) for k in reach if y - k >= 0) \
                        and any(bottom(px[x, y + k]) for k in reach if y + k < H):
                    found[state].append((x, y))
    best = None
    for state, mid, top, bottom in (("on", green, red, white), ("off", navy, mauve, blue)):
        for pts in clumps(found[state], max(3, int(0.02 * W))):
            if len(pts) < 6 or (best and len(pts) <= len(best[1])):  # a few stray pixels aren't a ball
                continue
            xs, ys = sorted(p[0] for p in pts), sorted(p[1] for p in pts)
            cx, cy = xs[len(xs) // 2], ys[len(ys) // 2]
            if whole(px, W, H, cx, cy, top, bottom):
                best = (state, pts, cx, cy)
    if not best:
        return None
    return best[0], best[2] / W, best[3] / H


def whole(px, W, H, cx, cy, top, bottom):
    """a whole ball round (cx, cy): its top colour fills the band just above the middle, its bottom colour the band
    just below. A real ball fills 0.66+ of both (on or off, Pixel); the night map's look-alikes (the moon weather icon,
    a gym behind the icon column) fill 0.2 or less (2026-11-12)"""
    r = max(4, int(0.025 * W))
    def share(ok, y0, y1):
        got = [ok(px[x, y]) for x in range(max(0, cx - r), min(W, cx + r + 1)) for y in range(max(0, y0), min(H, y1))]
        return sum(got) / len(got) if got else 0
    return share(top, cy - int(1.4 * r), cy - r // 2) >= 0.5 and share(bottom, cy + r // 2, cy + int(1.4 * r)) >= 0.5


def clumps(pts, cell):
    """pts in clumps, biggest first: points in touching cells of size cell are one clump"""
    cells = {}
    for p in pts:
        cells.setdefault((p[0] // cell, p[1] // cell), []).append(p)
    out, seen = [], set()
    for c in cells:
        if c in seen:
            continue
        seen.add(c)
        todo, clump = [c], []
        while todo:
            cx, cy = todo.pop()
            clump += cells[(cx, cy)]
            for n in ((cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                if n in cells and n not in seen:
                    seen.add(n)
                    todo.append(n)
        out.append(clump)
    return sorted(out, key=len, reverse=True)


def read():
    """-> (ball(), path, bounds)"""
    path, bounds = ui.capture()
    return ball(path), path, bounds


def map_trainer(texts):
    """the trainer name under the profile picture, bottom left of the map. None: not read"""
    from difflib import SequenceMatcher  # the small name reads loosely: 'CyrilJan', 'CyrilJaı' (Pixel, 2026-11-10)
    near = lambda a, b: SequenceMatcher(None, home.squash(a), home.squash(b)).ratio() >= 0.8
    got = [n for n in home.TRAINERS if any(near(n, t[4]) for t in texts if t[1] > 0.85 and t[0] < 0.5)]
    return got[0] if len(got) == 1 else None


def find():
    """the ball on the map, or None. Waits out the map's top right still loading, and a banner over it (a gift opened)"""
    return base.settle(lambda: read()[0], lambda b: b is not None, timeout=10)


def connect():
    """on the map: the ball off -> tapped, and on. -> seconds it took"""
    got = find()
    if not got:
        keep_capture("noball")
        raise Stop("no GO Plus+ ball at the top right of the map")
    if got[0] == "on":
        log("the GO Plus+ is already connected: no tap")
        return 0
    t0 = time.time()
    for tap in (1, 2):  # a second tap: the first was lost, or it tried and gave up (the ball goes off again)
        _, _, bounds = read()
        log(f"  the ball is off at ({got[1]:.3f}, {got[2]:.3f}): tap {tap}")
        base.click(got[1], got[2], bounds, fuzz=0.004)
        now = base.settle(lambda: read()[0], lambda b: b is not None and b[0] == "on", timeout=CONNECT_TIMEOUT)
        if now and now[0] == "on":
            took = time.time() - t0
            log(f"connected in {took:.1f}s")
            return took
        if not now:  # the tap opened something (a PokéStop, a Pokémon): back to the map, and look again
            home.to_map()
            now = find()
            if not now:
                break
            if now[0] == "on":
                log("connected (seen back on the map)")
                return time.time() - t0
        got = now
    keep_capture("noconnect")
    raise Stop(f"the GO Plus+ didn't connect (2 taps, {CONNECT_TIMEOUT}s each). Its battery may be flat, or it's paired with "
               f"another phone")


def script(only_look):
    if not ui.ANDROID:
        raise Stop("goplus.py is Pixel only: a tap through iPhone Mirroring never connects (POGO_PHONE=android)")
    texts = home.to_map()
    who = map_trainer(texts)
    if not who:
        who = home.trainer(fast=False)  # off the profile, back on the map
        texts = home.to_map()
    log(f"signed in: {who}")
    if only_look:
        b = find()
        log(f"the ball: {b[0] if b else 'not seen'}" + (f" at ({b[1]:.3f}, {b[2]:.3f})" if b else ""))
        return
    if who != FOR:
        if who:  # another trainer read for sure; an unread name is a stop like any other (it tries again)
            timer.off("goplus")
            log(f"goplus timer off till a {FOR} run connects")
        raise Stop(f"the GO Plus+ only connects on {FOR} ({who} is signed in): pogo.py account {FOR}, then this")
    connect()
    log(f"next goplus run in {AGAIN} min, at {timer.later('goplus', AGAIN)}")


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--look", action="store_true", help="say what the ball shows, no tap")
    a = ap.parse_args()
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="android" if ui.ANDROID else "ios")
    session.main(script, a.look)


if __name__ == "__main__":
    main()
