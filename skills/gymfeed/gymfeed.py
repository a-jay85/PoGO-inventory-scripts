#!/usr/bin/env python3
"""Feed berries to the Pokémon in the gyms you're defending, from the gym badge list.

  POGO_PHONE=android caffeinate -dimsu python3 gymfeed.py [--limit N]   the Android phone
  caffeinate -dimsu python3 gymfeed.py [--limit N]                      the iPhone

- Profile (ME tab), down to GYM BADGES, LIST. Sorts the badges by Defending (shield, arrow down): the gyms you're
  in come first. The list forgets its sort each time it opens, so it sorts every time.
- Opens the first badge that isn't gold and wasn't done this run. A gold badge has no meter under it.
- Taps TIME DEFENDING on the badge to go into the gym. A badge with no TIME DEFENDING: none of yours left in a gym,
  so the run ends. A gym with a raid on is skipped.
- Taps each Pokémon in the gym view, right-most first, lower if nothing new opens (a back-row one shows only a bit).
  On its page it picks a berry from the berry menu (FEEDABLE: Razz, Nanab, Pinap, each down to a floor; never Golden
  Razz or Silver Pinap), taps the floating berry every 1.5 s until it goes away (full for now), then the round X back
  to the gym view. No berry to spare: the run ends.
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
BERRY_MENU = (0.12, 0.90)  # the round berry button at its lower left: opens the BERRIES menu (Pixel, 2026-10-28)
OFF_MENU = (0.5, 0.30)  # a tap above the BERRIES menu shuts it with nothing picked
# the berries fed, in this order, and how many of each to leave in the bag. Golden Razz and Silver Pinap: never.
# The page opens on Razz for each Pokémon, so the kind is picked from the menu each time
FEEDABLE = {"RAZZ": 1, "NANAB": 1, "PINAP": 30}
# how far below its CP label to tap a Pokémon in the gym view. A back-row one shows only a bit between the ones in
# front: the Dragonite behind a Blissey opened at 0.125, not at 0.08 (2026-10-28)
TAP_DROPS = (0.08, 0.125, 0.165)
FEED_GAP = 1.5  # seconds from one berry tap to the next. Tested on the Pixel 2026-10-28, seconds per Pokémon for
# 10-11 berries: 2.5 s -> 26-28, 2.0 -> 30-34 (the count reads late), 1.5 -> 24 (about 1 tap in 12 lost), 1.0 -> 30
# (half the taps lost)
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
# a gym view's CP label as OCR reads it over the busy gym: 'CP2407', 'P633', '฿633', 'GP2940', 'g2855', '2833'
LABEL_RE = re.compile(r"^\W*[^\W\d]{0,2}\s*\d{2,4}\W*$")
# '0d 3h 7m' on a gym Pokémon's page. OCR reads any 0 as O: 'Od 3h 7m.', 'Od 12h Om'
DEFEND_RE = re.compile(r"\b[0-9O]+d\s*[0-9O]+h\s*[0-9O]+m")


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
    if "BERRIES" in words and "RAZZ BERRY" in j.upper():
        return "berrymenu"
    if any(DEFEND_RE.search(t[4]) and t[1] < 0.22 for t in texts):
        return "feed"
    if any(CP_RE.match(t[4].strip()) and 0.3 < t[1] < 0.66 for t in texts) \
            and any(t[1] < 0.18 and t[2] > 0.15 for t in texts if not CP_RE.match(t[4])):
        return "gymview"
    return home.where(path, texts)


def look():
    return base.look(where)


def cp_labels(texts):
    """the gym view's CP labels over its Pokémon -> [(cx, cy)]"""
    return [(t[0] + t[2] / 2, t[1] + t[3] / 2) for t in texts
            if LABEL_RE.match(t[4].strip()) and 0.3 < t[1] < 0.66 and t[3] < 0.04]


def all_labels():
    """the gym view's CP labels from two looks (OCR misses one now and then: the Pokémon bob) -> [(cx, cy)]"""
    labels = cp_labels(look()[1])
    time.sleep(0.5)
    for c in cp_labels(look()[1]):
        if all(abs(c[0] - o[0]) > 0.06 or abs(c[1] - o[1]) > 0.03 for o in labels):
            labels.append(c)
    return labels


def berries(texts):
    """the number under the floating berry (Android: lower right of it), or None: not read. OCR often misses a
    small 1-digit count on Android: berry_count() looks closer"""
    for t in texts:
        s = t[4].strip()
        if re.fullmatch(r"\d{1,4}", s) and 0.84 < t[1] < 0.92 and 0.38 < t[0] + t[2] / 2 < 0.72:
            return int(s)
    return None


def berry_count(texts):
    """berries() from a look, or on Android from a sharp crop of the count: OCR of the whole screen often misses a
    small 1-digit count there"""
    count = berries(texts)
    if count is None and ui.ANDROID:
        from PIL import Image
        im = Image.open(ui.android.sharp())
        W, H = im.size
        x0, y0, x1, y1 = 0.38, 0.84, 0.78, 0.93
        crop = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
        crop.resize((crop.width * 2, crop.height * 2)).save("/tmp/gymfeed_count.png")
        for t in ui.ocr("/tmp/gymfeed_count.png"):
            if re.fullmatch(r"\d{1,4}", t[4].strip()):
                return int(t[4].strip())
    return count


def berry_menu(texts):
    """the BERRIES menu -> {kind: (count or None: not read, where to tap its berry)}. kinds: RAZZ NANAB PINAP GOLDEN
    SILVER, from the names under the berries ('GOLDEN RAZZ' / 'BERRY'); the count ('x184') sits above the name"""
    out = {}
    for t in texts:
        m = re.match(r"(RAZZ|NANAB|PINAP|GOLDEN|SILVER)\b", ui.norm(t[4]))
        if not m or t[1] < 0.6:
            continue
        cx = t[0] + t[2] / 2
        num = [c for c in texts if re.fullmatch(r"[xX×]\s*\d{1,4}", c[4].strip())
               and 0 < t[1] - c[1] < 0.07 and abs(c[0] + c[2] / 2 - cx) < 0.13]
        out[m.group(1)] = (int(re.sub(r"\D", "", num[0][4])) if len(num) == 1 else None, (cx, t[1] - 0.07))
    return out


def who(texts):
    """one gym Pokémon's page -> (its name, its trainer): the name at the top, the trainer beside its CP"""
    top = [t for t in texts if (0.05 if ui.ANDROID else 0.08) < t[1] < 0.13 and not re.fullmatch(r"\W*[cC][pP]?\s*\d+\W*", t[4].strip())]
    name = " ".join(t[4].strip() for t in sorted(top, key=lambda t: t[0]))
    mid = [t[4].strip() for t in texts if 0.3 < t[1] < 0.5 and not LABEL_RE.match(t[4].strip())
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
    """the badge list sorted by Defending, arrow down. The menu shows DEFENDING with no arrow (another sort) or arrow
    up; one tap on it makes it arrow down and shuts the menu (every run that opened the menu again to check saw it
    down). A 2nd tap would turn it up, so: read the arrow first, tap only when it isn't down"""
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
    else:
        base.tap_box(hit, bounds)
    base.wait_for("badgelist", look=look, timeout=6)
    time.sleep(0.8)  # the tiles shuffle into place


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
            elif re.search(r"ADD FRIEND|SENT YOU A GIFT|DAYS AGO|HOURS? AGO|MINUTES? AGO", ui.joined(texts).upper()):
                # the FRIENDS tab (where /gift leaves it), maybe scrolled past its ADD FRIEND
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
    """a badge open -> "gym" once in its gym view. "none": no TIME DEFENDING (none of yours is in it). "raid": a raid
    is on there (the tap shows 'Raid in progress! Your Pokémon will return to the Gym once the raid is over.').
    "shut": two taps and no gym view"""
    screen, texts, _, bounds = base.wait_for("badge", look=look, timeout=20)  # it loads slowly now and then
    time.sleep(0.6)  # the defender and its timer fade in
    _, texts, _, bounds = look()
    hit = [t for t in texts if ui.norm(t[4]) == "TIME DEFENDING"]
    if not hit:
        return "none"
    for _ in range(2):
        base.tap_box(hit[0], bounds)
        try:
            base.wait_for("gymview", look=look, timeout=8, capture=False)
            time.sleep(1.5)  # the Pokémon walk in and their CP labels settle
            return "gym"
        except base.Lost:
            _, texts, _, bounds = look()
            if "RAID IN PROGRESS" in ui.joined(texts).upper():
                return "raid"
    keep_capture("nogym")
    return "shut"  # a raid whose words came and went, most likely: the next run tries again


# ---------- one Pokémon ----------

out_of_berries = False  # set when no FEEDABLE kind has more than its floor: the run ends
spent = set()  # kinds fed down to their floor this run: not picked again


def choose():
    """on a gym Pokémon's page: the BERRIES menu, the first FEEDABLE kind with more than its floor picked
    -> (kind, its count), or None: none to spare (the menu shut again, out_of_berries set)"""
    global out_of_berries
    base.click(*BERRY_MENU, look()[3], fuzz=0.01)
    base.wait_for("berrymenu", look=look, timeout=6)
    seen = []
    while len(seen) < 2 or seen[-1] != seen[-2]:  # it slides up: two reads in a row must agree
        time.sleep(0.4)
        _, texts, _, bounds = look()
        menu = berry_menu(texts)
        seen.append({k: c for k, (c, _) in menu.items()})
        if len(seen) > 6:
            break
    log("    bag: " + ", ".join(f"{k} {c}" for k, c in seen[-1].items()))
    for kind, floor in FEEDABLE.items():
        count, spot = menu.get(kind, (None, None))
        if count is not None and count > floor and kind not in spent:
            base.click(*spot, bounds, fuzz=0.01)
            base.wait_for("feed", look=look, timeout=6)
            time.sleep(0.8)  # the picked berry floats in
            return kind, count
    base.click(*OFF_MENU, bounds)
    base.wait_for("feed", look=look, timeout=6)
    out_of_berries = True
    return None


def feed(kind, have, left):
    """on a gym Pokémon's page with `kind` picked (`have` in the bag): the berry every FEED_GAP s while it floats,
    the bag keeps more than FEEDABLE[kind] and fewer than `left` are fed -> (berries fed, why it stopped: "full",
    "floor", "limit" or "stuck"). A berry counts when the number under it goes down"""
    floor = FEEDABLE[kind]
    _, texts, path, bounds = look()
    count = berry_count(texts)
    if count is None:
        return 0, "full"
    count = min(count, have)  # the menu's number and this one: the lower, in case one is misread high
    spare = min(have - floor, left)
    fed, stuck, taps, start, why = 0, 0, 0, time.time(), "limit"
    while fed < spare:
        if count <= floor:
            why = "floor"
            break
        t0 = time.time()
        base.click(*BERRY, bounds, fuzz=0.02)
        taps += 1
        time.sleep(max(0.0, t0 + FEED_GAP - time.time() - 0.6))
        _, texts, path, bounds = look()
        now = berry_count(texts)
        if now is None:  # gone, or a "+30 stardust" banner over it: look once more
            time.sleep(0.6)
            _, texts, path, bounds = look()
            now = berry_count(texts)
        if now is not None and now < count:
            fed += count - now
            stuck = 0
        elif now is None:
            fed += 1  # the last one: the berry goes as it's eaten
            time.sleep(1.2)
            _, texts, path, bounds = look()
            now = berry_count(texts)
            if now is None:
                why = "full"
                break
        else:
            stuck += 1
            if stuck >= 4:
                keep_capture("berrystuck")
                log(f"    the berry count stayed {count} for {stuck} taps: moving on")
                why = "stuck"
                break
        count = now
    if fed >= spare and why == "limit" and spare < left:
        why = "floor"
    if why == "floor":
        spent.add(kind)
    log(f"    {kind}: {taps} taps in {time.time() - start:.0f}s, {why}")
    return fed, why


# ---------- one gym ----------

def wait_feed(timeout=4):
    try:
        return base.wait_for("feed", look=look, timeout=timeout, capture=False)
    except base.Lost:
        return None


def feed_here(seen, total, limit):
    """on a gym Pokémon's page: feed it if it's new -> berries fed"""
    _, texts, path, _ = look()
    me = who(texts)
    if me in seen:
        return 0
    seen.add(me)
    if total >= limit or out_of_berries:
        return 0
    if berry_count(texts) is None:  # it floats in late
        time.sleep(1.0)
        if berry_count(look()[1]) is None:
            log(f"  {me[0]} ({me[1]}): full")
            return 0
    got = 0
    while total + got < limit:
        picked = choose()
        if not picked:
            log(f"  no berry to spare: every kind is down to what's kept ("
                + ", ".join(f"{k} {n}" for k, n in FEEDABLE.items()) + ")")
            break
        n, why = feed(*picked, limit - total - got)
        got += n
        if why != "floor":
            break
    log(f"  {me[0]} ({me[1]}): fed {got}")
    return got


def open_at(cx, cy, bounds, seen):
    """in the gym view: tap a Pokémon at TAP_DROPS under its CP label until one not seen yet opens -> the drop that
    opened it, on its page. None: back in the gym view, nothing new opened"""
    for drop in TAP_DROPS:
        base.click(cx, cy + drop, bounds, fuzz=0.01)
        if not wait_feed():
            log(f"    tap {cx:.2f},{cy + drop:.2f}: nothing opened")
            continue
        me = who(look()[1])
        if me not in seen:
            return drop
        log(f"    tap {cx:.2f},{cy + drop:.2f}: {me[0]} again")
        base.click(*X_BUTTON, look()[3], fuzz=0.006)  # one already fed: the tap went to the one in front
        _, _, _, bounds = base.wait_for("gymview", look=look, timeout=8)
        time.sleep(0.8)
    return None


def gym(total, limit):
    """in a gym's view: feed every Pokémon in it -> berries fed here"""
    labels = sorted(all_labels(), key=lambda c: -c[0])
    _, _, _, bounds = look()
    n = len(labels)
    log(f"  {n} Pokémon in the gym view")
    seen, fed, todo = set(), 0, labels
    # right-most first. A label whose first tap opened nothing new may have opened the one in front of it (not seen
    # yet then): a 2nd pass over those, with the front ones seen, reaches the one behind
    for _ in range(2):
        missed = []
        for cx, cy in todo:
            if total + fed >= limit or out_of_berries:
                return fed
            drop = open_at(cx, cy, bounds, seen)
            if drop is None:
                missed.append((cx, cy))
                continue
            if drop != TAP_DROPS[0]:
                missed.append((cx, cy))  # unsure it's this label's one
            fed += feed_here(seen, total + fed, limit)
            base.click(*X_BUTTON, look()[3], fuzz=0.006)
            _, _, _, bounds = base.wait_for("gymview", look=look, timeout=8)
            time.sleep(0.8)
        if len(seen) >= n or not missed:
            break
        todo = missed
    if len(seen) >= n or total + fed >= limit or out_of_berries:
        return fed
    log(f"  {len(missed)} didn't open on a tap: looking by swiping")
    # into the front Pokémon nearest the first one missed, then try each swipe from every page reached
    if seen:
        mx, my = missed[0] if missed else (0.5, 0.45)
        opened = [c for c in labels if c not in missed] or labels
        cx, cy = min(opened, key=lambda c: abs(c[0] - mx) + (0 if c[1] > my else 0.5))
        base.click(cx, cy + TAP_DROPS[0], bounds, fuzz=0.01)
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
    while len(seen) < n and used < MAX_SWIPES and total + fed < limit and not out_of_berries:
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
        inside = into_gym()
        if inside == "none":
            log(f"{name}: no TIME DEFENDING, so no gym of yours is left")
            break
        if inside != "gym":
            log(f"{name}: " + ("a raid is on there" if inside == "raid" else "the gym didn't open") + ", skipped")
            continue
        log(f"--- {name}")
        total += gym(total, limit)
        log(f"  {total} berries so far")
        if out_of_berries:
            break
    if total >= limit:
        log(f"--limit {limit} reached")
    log(f"done: {total} berries fed, {time.time() - t0:.0f}s")
    to_badge_list()  # out of the gym
    for _ in range(4):  # badge list -> profile -> map: the next script starts from the map
        screen, _, _, bounds = look()
        if screen not in ("badgelist", "profile"):
            break
        base.click(*X_BUTTON, bounds, fuzz=0.006)
        time.sleep(1.5)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--limit", type=int, default=LIMIT, help=f"at most N berries this run (default {LIMIT})")
    a = ap.parse_args()
    base.new_run_dir(os.path.join(HERE, "runs"), suffix=PHONE)
    session.main(script, a.limit)


if __name__ == "__main__":
    main()
