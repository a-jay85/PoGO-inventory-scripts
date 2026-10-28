#!/usr/bin/env python3
"""Feed berries to the Pokémon in the gyms you're defending, from the gym badge list.

  POGO_PHONE=android caffeinate -dimsu python3 gymfeed.py [--limit N]   the Android phone
  caffeinate -dimsu python3 gymfeed.py [--limit N]                      the iPhone

- Profile (ME tab), down to GYM BADGES, LIST. Sorts the badges by Defending (shield, arrow down): the gyms you're
  in come first. The list forgets its sort each time it opens, so it sorts every time.
- Opens the first badge that isn't gold and wasn't done this run. A gold badge has no meter under it.
- Taps TIME DEFENDING on the badge to go into the gym. A badge with no TIME DEFENDING: none of yours left in a gym,
  so the run ends.
- Taps each Pokémon in the gym view, right-most first. On its page it taps the floating berry every 2.5 s until the
  berry goes away (full for today), then the round X back to the gym view.
- A Pokémon a tap can't open (one in the back row, behind another) is found by swiping from the ones it did open.
  Some swipes only take with the finger held still first, on the spot where the hidden one shows.
- Back to the badge list, sorted again, the next badge. It ends after N berries (--limit, default 100) or when no
  gym is left.

A berry counts when the number under it goes down. Log in runs/<time>-<phone>/log.txt.
"""
import argparse, os, re, sys, time
from collections import deque

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, log, keep_capture
import home, session

PHONE = "android" if ui.ANDROID else "iphone"
X_BUTTON = (0.5, 0.937)  # the round X at the bottom middle: closes a Pokémon, the gym, the badge, the badge list
SORT_BUTTON = (0.85, 0.93)  # the badge list's sort button, bottom right; its menu's X sits in the same spot
BERRY = (0.5, 0.80)  # the floating berry on a gym Pokémon's page
FEED_GAP = 2.5  # seconds from one berry tap to the next (the user's pace)
LIMIT = 100
MAX_SWIPES = 24  # per gym, looking for Pokémon a tap didn't open

# swipes on a gym Pokémon's page: (x1, y1, x2, y2, hold ms). Left to right goes one way along the gym, right to
# left the other. A plain swipe on the lower half; the held ones start where a back-row Pokémon shows behind the
# front one's CP (the Dragonite behind a Blissey took a hold at 0.42, 0.38)
SWIPES = [
    (0.15, 0.62, 0.85, 0.62, None),
    (0.85, 0.62, 0.15, 0.62, None),
    (0.42, 0.38, 0.90, 0.38, 600),
    (0.58, 0.38, 0.10, 0.38, 600),
    (0.30, 0.38, 0.90, 0.38, 600),
    (0.70, 0.38, 0.10, 0.38, 600),
]

CP_RE = re.compile(r"^\W*[cC][pP]\s*\d{2,4}\W*$")
DEFEND_RE = re.compile(r"\b[0-9O]+d\s*\d+h\s*\d+m")  # '0d 3h 7m' (OCR: 'Od 3h 7m.') on a gym Pokémon's page


# ---------- reading ----------

def where(path, texts):
    """profile, badgelist, sortmenu, badge, gymview, feed, or what home.where says (map, mainmenu, exit ...)"""
    j = ui.joined(texts)
    words = {ui.norm(t[4]) for t in texts}
    if "DEFENDING" in words and any(w.startswith("NAME") for w in words) and "RECENT" in words:
        return "sortmenu"
    if "TIME DEFENDING" in j or "TOTAL GYM ACTIVITY" in j:
        return "badge"
    if {"ME", "FRIENDS"} <= words:  # (scrolled down, its GYM BADGES can sit near the top too)
        return "profile"
    if any(ui.norm(t[4]) == "GYM BADGES" and t[1] < 0.15 for t in texts):
        return "badgelist"
    if any(DEFEND_RE.search(t[4]) and t[1] < 0.22 for t in texts):
        return "feed"
    if len(cp_labels(texts)) >= 1 and any(t[1] < 0.18 and t[2] > 0.15 for t in texts if not CP_RE.match(t[4])):
        return "gymview"
    return home.where(path, texts)


def look():
    return base.look(where)


def cp_labels(texts):
    """the gym view's CP labels over its Pokémon -> [(cx, cy)]"""
    return [(t[0] + t[2] / 2, t[1] + t[3] / 2) for t in texts if CP_RE.match(t[4].strip()) and 0.3 < t[1] < 0.66]


def berries(texts):
    """the number under the floating berry (berries left), or None: no berry, this one's full"""
    for t in texts:
        s = t[4].strip()
        if re.fullmatch(r"\d{1,4}", s) and 0.84 < t[1] < 0.92 and 0.38 < t[0] + t[2] / 2 < 0.62:
            return int(s)
    return None


def who(texts):
    """one gym Pokémon's page -> (its name, its trainer): the name at the top, the trainer beside its CP"""
    top = [t for t in texts if 0.08 < t[1] < 0.13]
    name = " ".join(t[4].strip() for t in sorted(top, key=lambda t: t[0]))
    mid = [t[4].strip() for t in texts if 0.3 < t[1] < 0.5 and not CP_RE.match(t[4].strip())
           and not re.fullmatch(r"[\d\W]+", t[4].strip()) and len(t[4].strip()) > 2]
    return name, " ".join(sorted(mid))


def gym_name(texts):
    top = [t for t in texts if 0.08 < t[1] < 0.17 and t[0] > 0.2]
    return " ".join(t[4].strip() for t in sorted(top, key=lambda t: (round(t[1], 2), t[0])))


# ---------- the badge list ----------

def tiles(texts):
    """the badge list's tiles -> [(name, cx, top)]: the name under each badge (its lines joined), across the
    tile's middle, the top of its first line"""
    boxes = sorted((t for t in texts if 0.15 < t[1] < 0.9 and t[2] > 0.04), key=lambda t: (t[1], t[0]))
    cols = {}
    for t in boxes:
        cx = t[0] + t[2] / 2
        col = min((0.18, 0.5, 0.82), key=lambda c: abs(c - cx))
        lines = cols.setdefault(col, [])
        if lines and t[1] - lines[-1][-1][1] < 0.025:  # the 2nd line of the name above
            lines[-1].append(t)
        else:
            lines.append([t])
    out = []
    for col, names in cols.items():
        for parts in names:
            out.append((" ".join(p[4].strip() for p in parts), col, min(p[1] for p in parts)))
    return sorted(out, key=lambda o: (round(o[2] / 0.08), o[1]))


def is_meter(px):
    r, g, b = px
    teal = r < 140 and g > 190 and b > 180
    grey = max(px) - min(px) < 8 and 180 < r < 230
    return teal or grey


def has_meter(path, cx, top):
    """the progress meter under a badge (bronze, silver: it fills to the next one). A gold badge has none.
    A thin teal or grey bar 1-3 % of the screen above the name's first line (a one-line name sits a bit lower)"""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    W, H = im.size
    for fy in range(int((top - 0.035) * H), int((top - 0.004) * H)):
        run = best = 0
        for fx in range(int((cx - 0.1) * W), int((cx + 0.1) * W)):
            if is_meter(im.getpixel((fx, fy))):
                run += 1
                best = max(best, run)
            else:
                run = 0
        if best > 0.08 * W:
            return True
    return False


def arrow(path, cy):
    """the sort menu's small white arrow right of a row's icon -> 'down', 'up', or None (not this row's sort)"""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    W, H = im.size
    ys = range(int((cy - 0.02) * H), int((cy + 0.02) * H))
    bright = lambda fx, fy: min(im.getpixel((fx, fy))) > 150
    cols = [fx for fx in range(int(0.86 * W), int(0.97 * W)) if any(bright(fx, fy) for fy in ys)]
    if not cols:
        return None
    # the arrow is the right-most blob of columns; the shield's edge can show at the left (Android)
    x1 = x0 = cols[-1]
    while x0 - 1 in cols or x0 - 2 in cols:
        x0 -= 1
    rows = []
    for fy in ys:
        n = sum(bright(fx, fy) for fx in range(x0, x1 + 1))
        if n:
            rows.append((fy, n))
    if len(rows) < 5:
        return None
    # the head holds most of the ink: its weight sits below the middle on a down arrow
    weight = sum(fy * n for fy, n in rows) / sum(n for _, n in rows)
    return "down" if weight > (rows[0][0] + rows[-1][0]) / 2 else "up"


def sort_defending():
    """the badge list sorted by Defending, arrow down. It opens on Recent; a tap on DEFENDING sorts by it (arrow
    down), a 2nd tap turns the arrow up. So: read the arrow in the menu, tap until it's down, close the menu"""
    for _ in range(3):
        _, _, _, bounds = base.wait_for("badgelist", look=look, timeout=8)
        base.click(*SORT_BUTTON, bounds, fuzz=0.01)
        base.wait_for("sortmenu", look=look, timeout=6)
        seen = []
        while len(seen) < 2 or seen[-1] != seen[-2]:  # the menu slides in: two reads in a row must agree
            time.sleep(0.6)
            _, texts, path, bounds = look()
            hit = next(t for t in texts if ui.norm(t[4]) == "DEFENDING")
            seen.append(arrow(path, hit[1] + hit[3] / 2))
            if len(seen) > 6:
                break
        if seen[-1] == "down":
            base.click(*SORT_BUTTON, bounds, fuzz=0.01)  # its X sits where the sort button was
            time.sleep(1.0)
            base.wait_for("badgelist", look=look, timeout=6)
            time.sleep(0.8)  # the tiles shuffle into place
            return
        base.tap_box(hit, bounds)
        time.sleep(1.5)
    keep_capture("sort")
    raise Stop("couldn't sort the gym badges by Defending, arrow down")


def pick(done):
    """sorted badge list -> (name, the tile to tap) of the first badge not gold and not done yet, or None.
    Scrolls down a screen at most twice"""
    for page in range(3):
        _, texts, path, bounds = look()
        for name, cx, top in tiles(texts):
            if name in done:
                continue
            if not has_meter(path, cx, top):
                log(f"  {name}: gold, skipped")
                done.add(name)
                continue
            return name, (cx, top - 0.09), bounds
        if page < 2:
            base.drag(0.5, 0.8, 0.5, 0.35, bounds, android_settle=base.LIST_SETTLE)
    return None


# ---------- getting around ----------

def to_badge_list():
    """from wherever (a gym, a badge, the profile, the map) to the gym badge list"""
    scrolls = 0
    for _ in range(25):
        screen, texts, path, bounds = look()
        if screen == "badgelist":
            return
        if screen in ("feed", "gymview", "badge", "sortmenu"):
            base.click(*(SORT_BUTTON if screen == "sortmenu" else X_BUTTON), bounds, fuzz=0.006)
            time.sleep(1.5)
        elif screen == "profile":
            gb = [t for t in texts if ui.norm(t[4]) == "GYM BADGES"]
            lst = [t for t in texts if gb and ui.norm(t[4]).startswith("LIST") and t[1] > gb[0][1]]
            if lst and lst[0][1] < 0.85:
                base.tap_box(lst[0], bounds, dy=-0.03)  # the green diamond over LIST >
                time.sleep(2.0)
            elif "FRIENDS" in ui.joined(texts) and "ADD FRIEND" in ui.joined(texts):
                home.press_text(texts, bounds, "ME")  # the profile opens on its last tab
                time.sleep(1.5)
            elif scrolls < 8:
                scrolls += 1
                base.drag(0.5, 0.85, 0.5, 0.45 if gb else 0.3, bounds)
            else:
                keep_capture("nobadges")
                raise Stop("scrolled the profile and found no GYM BADGES ... LIST")
        elif screen == "map":
            base.click(0.13, 0.91, bounds)  # the profile picture
            time.sleep(2.0)
        elif screen == "mainmenu":
            if ui.ANDROID:
                ui.android.key("back")
            else:
                base.click(*X_BUTTON, bounds)
            time.sleep(1.5)
        elif screen in ("list", "tag-tab") or screen in home.OPEN:
            home.start(storage=True)  # the Pokémon screens: out to the map the known way
            base.click(*X_BUTTON, base.look()[3])
            time.sleep(1.5)
        elif screen == "exit":
            home.press_text(texts, bounds, "CANCEL")
            time.sleep(1.5)
        else:
            home.unstick(texts)
    keep_capture("nobadgelist")
    raise Stop("couldn't get to the gym badge list")


def into_gym():
    """a badge open -> True once in its gym view. False: no TIME DEFENDING (none of yours is in it)"""
    screen, texts, _, bounds = base.wait_for("badge", look=look, timeout=8)
    time.sleep(0.6)  # the defender and its timer fade in
    _, texts, _, bounds = look()
    hit = [t for t in texts if ui.norm(t[4]) == "TIME DEFENDING"]
    if not hit:
        return False
    base.tap_box(hit[0], bounds)
    base.wait_for("gymview", look=look, timeout=15)
    time.sleep(1.5)  # the Pokémon walk in and their CP labels settle
    return True


# ---------- one Pokémon ----------

def feed(left):
    """on a gym Pokémon's page: the berry every FEED_GAP s until it goes away, at most `left` berries -> berries fed"""
    _, texts, _, bounds = look()
    count = berries(texts)
    fed, stuck = 0, 0
    while count is not None and fed < left:
        t0 = time.time()
        base.click(*BERRY, bounds, fuzz=0.02)
        time.sleep(max(0.0, t0 + FEED_GAP - time.time() - 0.6))
        _, texts, _, bounds = look()
        now = berries(texts)
        if now is None:  # gone, or a "+30 stardust" banner over it: look once more
            time.sleep(0.6)
            _, texts, _, bounds = look()
            now = berries(texts)
        if now is not None and now < count:
            fed += count - now
            stuck = 0
        elif now is None:
            fed += 1  # the last one: the berry goes as it's eaten
        else:
            stuck += 1
            if stuck >= 4:
                keep_capture("berrystuck")
                log(f"    the berry count stayed {count} for {stuck} taps: moving on")
                break
        count = now
    return fed


# ---------- one gym ----------

def wait_feed(timeout=4):
    try:
        return base.wait_for("feed", look=look, timeout=timeout, capture=False)
    except base.Lost:
        return None


def feed_here(seen, total, limit):
    """on a gym Pokémon's page: feed it if it's new -> berries fed"""
    _, texts, _, _ = look()
    me = who(texts)
    if me in seen:
        return 0
    seen.add(me)
    if total >= limit:
        return 0
    if berries(texts) is None:
        log(f"  {me[0]} ({me[1]}): full")
        return 0
    got = feed(limit - total)
    log(f"  {me[0]} ({me[1]}): fed {got}")
    return got


def gym(total, limit):
    """in a gym's view: feed every Pokémon in it -> berries fed here"""
    _, texts, _, bounds = look()
    labels = sorted(cp_labels(texts), key=lambda c: -c[0])
    n = len(labels)
    log(f"  {n} Pokémon in the gym view")
    seen, fed, missed = set(), 0, []
    for cx, cy in labels:  # right-most first
        if total + fed >= limit:
            return fed
        base.click(cx, cy + 0.08, bounds, fuzz=0.01)
        if not wait_feed():
            missed.append((cx, cy))
            continue
        fed += feed_here(seen, total + fed, limit)
        base.click(*X_BUTTON, look()[3], fuzz=0.006)
        _, _, _, bounds = base.wait_for("gymview", look=look, timeout=8)
        time.sleep(0.8)
    if len(seen) >= n or total + fed >= limit:
        return fed
    log(f"  {len(missed)} didn't open on a tap: looking by swiping")
    # into the front Pokémon nearest the first one missed, then try each swipe from every page reached
    if seen:
        mx, my = missed[0] if missed else (0.5, 0.45)
        opened = [c for c in labels if c not in missed] or labels
        cx, cy = min(opened, key=lambda c: abs(c[0] - mx) + (0 if c[1] > my else 0.5))
        base.click(cx, cy + 0.08, bounds, fuzz=0.01)
        if not wait_feed():
            log("  couldn't open a Pokémon to swipe from")
            return fed
    else:
        return fed
    fed += explore(seen, n, total + fed, limit)
    base.click(*X_BUTTON, look()[3], fuzz=0.006)
    base.wait_for("gymview", look=look, timeout=8)
    return fed


def explore(seen, n, total, limit):
    """on a gym Pokémon's page: try SWIPES from each page reached until n are seen or nothing's left to try.
    -> berries fed. Each page is known by its name and trainer; a path of swipes leads back to one with swipes left"""
    edges = {}  # page -> {swipe: page it led to}
    here, fed, used = who(look()[1]), 0, 0
    while len(seen) < n and used < MAX_SWIPES and total + fed < limit:
        todo = [i for i in range(len(SWIPES)) if i not in edges.get(here, {})]
        if todo:
            path = [todo[0]]
        else:  # the nearest page with a swipe not tried yet
            path = route(edges, here)
            if not path:
                break
        for i in path:
            x1, y1, x2, y2, hold = SWIPES[i]
            _, _, _, bounds = look()
            base.drag(x1, y1, x2, y2, bounds, ms=450, hold=hold, settle=(1.0, 1.3))
            used += 1
            if not wait_feed(3):
                keep_capture("swipelost")
                raise Stop("a swipe in the gym left the Pokémon page")
            now = who(look()[1])
            edges.setdefault(here, {})[i] = now
            if now not in seen:
                fed += feed_here(seen, total + fed, limit)
            here = now
    return fed


def route(edges, start):
    """-> the swipes from start to the nearest page with an untried swipe (then that swipe), or None"""
    q, back = deque([start]), {start: None}
    while q:
        p = q.popleft()
        todo = [i for i in range(len(SWIPES)) if i not in edges.get(p, {})]
        if todo and p != start:
            path = [todo[0]]
            while back[p]:
                p, i = back[p]
                path.insert(0, i)
            return path
        for i, nxt in edges.get(p, {}).items():
            if nxt not in back:
                back[nxt] = (p, i)
                q.append(nxt)
    return None


# ---------- the run ----------

def script(limit):
    total, done, t0 = 0, set(), time.time()
    home.start(storage=False)
    while total < limit:
        to_badge_list()
        sort_defending()
        got = pick(done)
        if not got:
            log("no badge left that isn't gold")
            break
        name, (fx, fy), bounds = got
        done.add(name)
        base.click(fx, fy, bounds, fuzz=0.01)
        if not into_gym():
            log(f"{name}: no TIME DEFENDING, so no gym of yours is left")
            break
        log(f"--- {name}")
        total += gym(total, limit)
        log(f"  {total} berries so far")
    if total >= limit:
        log(f"--limit {limit} reached")
    log(f"done: {total} berries fed, {time.time() - t0:.0f}s")
    to_badge_list()  # out of the gym
    base.click(*X_BUTTON, look()[3], fuzz=0.006)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--limit", type=int, default=LIMIT, help=f"at most N berries this run (default {LIMIT})")
    a = ap.parse_args()
    base.new_run_dir(os.path.join(HERE, "runs"), suffix=PHONE)
    session.main(script, a.limit)


if __name__ == "__main__":
    main()
