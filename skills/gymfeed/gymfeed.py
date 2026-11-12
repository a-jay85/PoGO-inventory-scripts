#!/usr/bin/env python3
"""Feed berries to the Pokémon in the gyms you're defending, from the gym badge list.

  POGO_PHONE=android caffeinate -dimsu python3 gymfeed.py [--limit N]   the Android phone
  caffeinate -dimsu python3 gymfeed.py [--limit N]                      the iPhone

- Profile (ME tab), down to GYM BADGES, LIST. Sorts the badges by Defending (shield, arrow down): the gyms you're
  in come first. The list forgets its sort each time it opens, so it sorts every time.
- Opens the first badge that isn't gold and wasn't done this run. A gold badge has no meter under it and a gold
  frame. Only badges with the small defender bubble at their top left count: the first one without it ends the
  run (the sort puts the gyms you're in first).
- Taps TIME DEFENDING on the badge to go into the gym. A badge with no TIME DEFENDING: none of yours left in a gym,
  so the run ends. A gym with a raid on is skipped.
- Taps each Pokémon in the gym view, right-most first, lower if nothing new opens (a back-row one shows only a bit).
  On its page it picks a berry from the berry menu (FEEDABLE: Razz, Nanab, Pinap, each down to a floor; never Golden
  Razz or Silver Pinap), taps the floating berry about every 2.5 s until it stays gone for 2 s (full for now: the
  game takes 10 per Pokémon per 30 min; a picture is kept), then the round X back to the gym view. No berry to spare: the run ends. It looks again right before each
  tap: a tap with no berry there hits the faint Pokémon behind and jumps to its page. If the page did change, feeding
  stops (a picture is kept) and that one gets its turn later.
- The CP labels undercount a gym (one in the back row may have none), so after the taps it always swipes from the
  ones it opened, until 6 are seen or no swipe is left to try. Some swipes only take with the finger held still
  first, on the spot where the hidden one shows.
- Back to the badge list, sorted again, the next badge. It ends after N berries (--limit, default 100) or when no
  gym is left.

A berry counts when it's tapped while floating. Whether one floats is read from its colours, not from the number
beside it: that number is how many berries the Pokémon got since it went into the gym (the user, 2026-11-08). The
bag counts come from the berry menu. Log in runs/<time>-<phone>/log.txt.

At the end of a run that wasn't stopped, it tells a local timer whether any gym is left to feed: it runs
~/.config/pogo/gymfeed_timer with "on" (a gym of yours that isn't gold: fed, full, or a raid on) or "off" (every
badge gold, or none of yours in a gym). A gym that didn't open leaves the timer as it is. No such file: nothing.

A run that hit --limit or ran out of spare berries also says "on". The timer only turns back on through a run that
finds a gym: switching accounts doesn't. The berry menu was measured on the Pixel only.
"""
import argparse, os, re, subprocess, sys, time
from collections import Counter, deque
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log, keep_capture
import home, session, pages

PHONE = "android" if ui.ANDROID else "iphone"
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
BERRY_WAIT = 1.1  # seconds from a berry tap to the look before the next. The screenshot must come about 2 s after the
# tap: at 1.3 s the number still showed on a full Pokémon, then the next tap hit no berry and jumped (2026-11-06)
LIMIT = 100
TIMER = os.path.expanduser("~/.config/pogo/gymfeed_timer")  # the local timer's on/off switch, out of the repo
MAX_SWIPES = 40  # per gym. Each swipe is about 3 s
SWIPE_STAYS = 4  # a swipe that stayed on the page this often isn't tried from there again. Most stays end with a retry:
# Chansey's left to right stayed twice in a row, then a run gave up on it and never found Scizor (2026-11-06)
GYM_SIZE = 6  # the most a gym holds. The CP labels can't count them: 4 labels, 5+ Pokémon on 2026-11-06
BERRY_SHARE = 0.03  # a floating Razz fills 7-22 % of BERRY_BOX with warm or green pixels and 24-32 % with magenta;
# no berry is 0 % of each (both phones, 2026-11-08). The Pixel's berry is darker: a test for bright colour missed it
BERRY_BOX = (0.36, 0.72, 0.64, 0.88)
MAX_TAPS = 14  # taps on one Pokémon at most: the game takes 10 per 30 min, so more means the taps aren't feeding
FULL_WAIT = 2.0  # seconds a berry must stay gone to call a Pokémon full

# swipes on a gym Pokémon's page: (x1, y1, x2, y2). The direction and the height pick who comes next, and the speed
# doesn't matter. In 130 swipes on a full gym (2026-11-06), right to left at 0.72 went round
# Chansey > Blissey > Greninja > Hitmonchan > Ampharos > Chansey, and left to right at 0.72 took Chansey to Scizor, the
# one off that ring. At 0.62 Greninja went to Ampharos 9 of 9, so that height misses Hitmonchan and Scizor. Held swipes
# higher up gave a different answer each time
SWIPES = [
    (0.85, 0.72, 0.15, 0.72),
    (0.15, 0.72, 0.85, 0.72),
    (0.85, 0.62, 0.15, 0.62),
    (0.15, 0.62, 0.85, 0.62),
]

CP_RE = pages.CP_RE
# a gym view's CP label as OCR reads it over the busy gym: 'CP2407', 'P633', '฿633', 'GP2940', 'g2855', '2833'
LABEL_RE = re.compile(r"^\W*[^\W\d]{0,2}\W?\s*\d{2,4}\W*$")  # and 'c*1677' (iPhone, 2026-11-08)
DEFEND_RE = pages.DEFEND_RE  # '0d 3h 7m' on a gym Pokémon's page


# ---------- reading ----------

def where(path, texts):
    """profile, badgelist, sortmenu, badge, gymview, feed, or what home.where says (map, mainmenu, exit ...)"""
    j = ui.joined(texts)
    words = {ui.norm(t[4]) for t in texts}
    if pages.gym_sortmenu(texts):
        return "sortmenu"
    if pages.gym_badge(texts):
        return "badge"
    if {"ME", "FRIENDS"} <= words:  # (scrolled down, its GYM BADGES can sit near the top too)
        return "profile"
    if pages.gym_badgelist(texts):
        return "badgelist"
    if "BERRIES" in words and "RAZZ BERRY" in j.upper():
        return "berrymenu"
    if pages.gym_feed(texts):
        return "feed"
    if gym_view(texts):
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


def berry_colours(path):
    """-> (share of warm or green pixels, share of magenta ones) in BERRY_BOX, where the berry floats. The gym floor
    behind is blue-grey"""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    W, H = im.size
    x0, y0, x1, y1 = BERRY_BOX
    c = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))).resize((60, 70))
    px = [c.getpixel((x, y)) for y in range(70) for x in range(60)]
    warm = sum(1 for r, g, b in px if (r - b > 30 or g - b > 30) and max(r, g, b) > 60)
    magenta = sum(1 for r, g, b in px if r - g > 40 and b - g > 20)
    return warm / len(px), magenta / len(px)


def berry_up(path):
    """a berry floats on this gym Pokémon's page: it's hungry. A Razz's purple counts as magenta more than warm"""
    return max(berry_colours(path)) >= BERRY_SHARE


def razz_up(path):
    """the berry floating is a Razz: magenta, where Nanab, Pinap and Golden Razz are yellow"""
    warm, magenta = berry_colours(path)
    return magenta >= BERRY_SHARE and magenta >= warm / 3


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


def menu_counts(menu, texts, path):
    """berry_menu() with each count it missed read again from a close crop of path. OCR of the whole screen misses a
    1-digit count ('x5' in its small bubble, the Razz at 5 on 2026-10-28). The bubble sits at the berry's lower
    left, left of its name's middle"""
    from PIL import Image
    im = Image.open(path)
    W, H = im.size
    out = dict(menu)
    for kind, (count, spot) in menu.items():
        if count is not None:
            continue
        t = next(t for t in texts if t[1] >= 0.6 and ui.norm(t[4]).startswith(kind))
        cx = t[0] + t[2] / 2
        x0, y0, x1, y1 = max(0.0, cx - 0.17), t[1] - 0.05, cx, t[1] - 0.002
        crop = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
        crop.resize((crop.width * 2, crop.height * 2)).save("/tmp/gymfeed_menu_count.png")
        nums = [m for c in ui.ocr("/tmp/gymfeed_menu_count.png") for m in [re.fullmatch(r"[xX×]?\s*(\d{1,4})", c[4].strip())] if m]
        if len(nums) == 1:
            out[kind] = (int(nums[0].group(1)), spot)
    return out


known = []  # the (name, trainer)s met in this gym. A gym holds one of each species, so the name alone says who


def like(a, b, enough):
    return SequenceMatcher(None, a, b).ratio() >= enough


def page_name(texts):
    """the name at the top of a gym Pokémon's page"""
    top = [t for t in texts if (0.05 if ui.ANDROID else 0.08) < t[1] < 0.13 and not re.fullmatch(r"\W*[cC][pP]?\s*\d+\W*", t[4].strip())]
    words = " ".join(t[4].strip() for t in sorted(top, key=lambda t: t[0])).split()
    return " ".join(w for w in words if not dust(w))


def dust(word):
    """a word of the '+10 STARDUST' that floats over the name after each berry: 'STABEUST', 'STARNUST•', '+10'.
    Left in, it made the page read as another Pokémon's and stopped the feeding (5 of 6 on 2026-11-08)"""
    letters = re.sub(r"[^A-Z]", "", word.upper())
    return bool(re.fullmatch(r"\+\d+\W*", word)) or (len(letters) >= 6 and like(letters, "STARDUST", 0.6))


def gym_view(texts):
    """pages.gym_view, or the same with the looser CP labels OCR reads over a busy gym ('GP2008,', 'c*1677'): the
    gym's name across the top, a label in the middle. With only those, it read as an unknown screen (2026-11-08)"""
    if pages.gym_view(texts):
        return True
    return any(LABEL_RE.match(t[4].strip()) and 0.3 < t[1] < 0.66 and t[3] < 0.04 for t in texts) \
        and any(t[1] < 0.18 and t[2] > 0.15 for t in texts if not LABEL_RE.match(t[4].strip()))


def who(texts):
    """one gym Pokémon's page -> (its name, its trainer): the name at the top, the trainer beside its CP. OCR reads the
    trainer over the busy gym differently each time ('Beidoutabao', '.2196 Beidubadhr'), and a page met before keeps
    its first read. A 2nd Ampharos read that way once made 6 seen with Scizor still unfound (2026-11-06)"""
    name = page_name(texts)
    mid = [t[4].strip() for t in texts if 0.3 < t[1] < 0.5 and not LABEL_RE.match(t[4].strip())
           and not re.fullmatch(r"[\d\W]+", t[4].strip()) and len(t[4].strip()) > 2]
    trainer = " ".join(sorted(mid))
    for k in known:
        if like(k[0], name, 0.8):
            return k
    known.append((name, trainer))
    return name, trainer


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
        tops = [min(p[1] for p in parts) for parts in names]
        for parts, top in zip(names, tops):
            # text on a badge's own picture, just above its name, isn't a name: Oracle Park's Giants logo read as
            # 'GANT)' (iPhone, 2026-11-08). Names in a column sit about 0.175 apart
            if any(0 < t - top < 0.1 for t in tops):
                continue
            out.append((" ".join(p[4].strip() for p in parts), col, top))
    return sorted(out, key=lambda o: (round(o[2] / 0.08), o[1]))


METER_GAP = 2  # pixels that aren't meter allowed inside one bar (see has_meter)


def is_meter(px):
    r, g, b = px
    teal = r < 140 and g > 190 and b > 180
    grey = max(px) - min(px) < 8 and 180 < r < 230
    return teal or grey


def has_meter(path, cx, top):
    """the progress meter under a badge (bronze, silver: it fills to the next one). A gold badge has none.
    A thin teal or grey bar 1-3 % of the screen above the name's first line (a one-line name sits a bit lower).
    Where the teal meets the grey sits a blended pixel, neither colour. On the small iPhone capture (406 px wide)
    that split Oracle Park's silver meter into two short pieces and it read as gold (2026-11-08): so up to
    METER_GAP pixels that aren't meter don't end the bar"""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    W, H = im.size
    for fy in range(int((top - 0.035) * H), int((top - 0.004) * H)):
        run = best = gap = 0
        for fx in range(int((cx - 0.1) * W), int((cx + 0.1) * W)):
            if is_meter(im.getpixel((fx, fy))):
                run, gap = run + 1, 0
                best = max(best, run)
            else:
                gap += 1
                if gap > METER_GAP:
                    run = 0
        if best > 0.08 * W:
            return True
    return False


def is_gold(px):
    r, g, b = px
    return r > 190 and 140 < g < 235 and b < 120 and r - b > 100


GOLD_SHARE = 0.02  # a gold badge's yellow frame: 4.3-5.6 % of the area round it; a silver one 0 % (iPhone, 2026-11-08)


def gold_frame(path, cx, top):
    """the badge above a name has a gold frame: yellow pixels make up GOLD_SHARE or more of the area round it
    (its photo sits inside the frame, so a yellow photo alone could add some)"""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = [im.getpixel((fx, fy)) for fy in range(int((top - 0.16) * H), int((top - 0.03) * H))
          for fx in range(int((cx - 0.09) * W), int((cx + 0.09) * W))]
    return bool(px) and sum(map(is_gold, px)) >= GOLD_SHARE * len(px)


DEFENDER_SHARE = 0.03  # the defender bubble's dark Pokémon: 11 % of its box; a badge without one 0-0.3 % (iPhone,
# 2026-11-08)


def defended(path, cx, top):
    """the small round bubble with a dark Pokémon at a badge's top left: one of yours is in that gym"""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = [im.getpixel((fx, fy)) for fy in range(int((top - 0.115) * H), int((top - 0.06) * H))
          for fx in range(max(0, int((cx - 0.13) * W)), int((cx - 0.05) * W))]
    return bool(px) and sum(1 for p in px if max(p) < 120) >= DEFENDER_SHARE * len(px)


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
        time.sleep(0.25)
        _, texts, path, bounds = look()
        hit = next(t for t in texts if ui.norm(t[4]) == "DEFENDING")
        seen.append(arrow(path, hit[1] + hit[3] / 2))
        if len(seen) > 6:
            break
    if seen[-1] == "down":
        base.click(*SORT_BUTTON, bounds, fuzz=0.01)  # its X sits where the sort button was
    else:
        base.tap_box(hit, bounds)
    base.wait_for("badgelist", look=look, timeout=6)
    time.sleep(0.5)  # the tiles shuffle into place


def fresh_list():
    """the gym badge list, opened anew so it starts at its top. The game keeps the list's scroll while it's open, and
    a run that started on a list left scrolled down saw gyms not yours first and ended. A drag down at the top shuts
    the list instead of scrolling (2026-11-08); shut and opened again it starts at the top"""
    to_badge_list()
    base.tap_x(look()[3], fuzz=0.006)
    off_screen("badgelist")
    to_badge_list()


def pick(done):
    """sorted badge list -> (name, the tile to tap) of the first badge not gold and not done yet, or None.
    Gold takes both reads: no meter under it and a gold frame. A badge that fails one is opened (one open too many
    costs a few seconds; a silver badge read as gold goes unfed). None also once a badge without the defender
    bubble shows: the sort put every gym of yours before it. Scrolls down a screen at most twice"""
    mine = False  # a defender bubble seen: only then does a badge without one end the list. The bubble was measured
    # on the iPhone only; a badge opened without one still ends the run by its missing TIME DEFENDING
    for page in range(3):
        _, texts, path, bounds = look()
        for name, cx, top in tiles(texts):
            if top < 0.25:  # its badge runs off the top of the list: a scroll left only part of it ('Statue')
                continue
            if defended(path, cx, top):
                mine = True
            elif mine:
                keep_capture("lastgym")
                log(f"  {name}: none of yours in it, so the gyms you're in end here")
                return None
            if name in done:
                continue
            meter, frame = has_meter(path, cx, top), gold_frame(path, cx, top)
            if not meter and frame:
                log(f"  {name}: gold, skipped")
                done.add(name)
                continue
            if meter == frame:
                log(f"  {name}: " + ("a meter but a gold frame" if meter else "no meter but not a gold frame")
                    + ", opened to be sure")
            return name, (cx, top - 0.09), bounds
        if page < 2:
            base.drag(0.5, 0.8, 0.5, 0.35, bounds, android_settle=base.LIST_SETTLE)
    return None


# ---------- getting around ----------

def off_screen(screen, timeout=3.0):
    """after a tap meant to leave `screen`: look until another screen the walk knows shows. Sooner than a fixed wait,
    and no 2nd tap on the way (a blank or half-drawn screen doesn't count)"""
    end = time.time() + timeout
    while time.time() < end:
        now = look()[0]
        if now not in (screen, "blank", "unknown"):
            return
        time.sleep(0.15)


def to_badge_list():
    """from wherever (a gym, a badge, the profile, the map) to the gym badge list"""
    scrolls = 0
    for _ in range(35):
        screen, texts, path, bounds = look()
        if screen == "badgelist":
            return
        if screen in ("feed", "gymview", "badge", "sortmenu"):
            base.click(*(SORT_BUTTON if screen == "sortmenu" else base.X_BUTTON), bounds, fuzz=0.006)
            off_screen(screen)
        elif screen == "profile":
            gb = [t for t in texts if ui.norm(t[4]) == "GYM BADGES"]
            lst = [t for t in texts if gb and ui.norm(t[4]).startswith("LIST") and t[1] > gb[0][1]]
            if lst and lst[0][1] < 0.85:
                base.tap_box(lst[0], bounds, dy=-0.03)  # the green diamond over LIST >
                off_screen(screen)
            elif re.search(r"ADD FRIEND|SENT YOU A GIFT|DAYS AGO|HOURS? AGO|MINUTES? AGO", ui.joined(texts).upper()):
                # the FRIENDS tab (where /gift leaves it), maybe scrolled past its ADD FRIEND
                home.press_text(texts, bounds, "ME")  # the profile opens on its last tab
                time.sleep(1.5)
            elif gb or scrolls < 8:
                scrolls += 1
                base.drag(0.5, 0.85, 0.5, 0.45 if gb else 0.12, bounds, android_settle=base.LIST_SETTLE)  # 0.9 starts on the bottom banner: no scroll
            elif scrolls < 20:  # the profile keeps its scroll: /gift can leave it down in the medals, past the badges
                scrolls += 1
                base.drag(0.5, 0.3, 0.5, 0.85, bounds)
            else:
                keep_capture("nobadges")
                raise Stop("scrolled the profile and found no GYM BADGES ... LIST")
        elif screen == "map":
            base.click(0.13, 0.91, bounds)  # the profile picture
            off_screen(screen)
        elif screen == "mainmenu":
            base.back_or_x(bounds)
            time.sleep(1.5)
        elif screen in ("list", "tag-tab") or screen in home.OPEN:
            home.start(storage=True)  # the Pokémon screens: out to the map the known way
            base.tap_x(base.look()[3])
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
razz_seen = None  # the Razz in the bag as last read this run. None: not read yet


def tap_to(spot, bounds, want, then):
    """a tap that should bring `want` from the `then` screen, again while `then` stays: the iPhone loses a tap now
    and then (NANAB in the menu, the berry button: two runs stopped there, 2026-11-08)"""
    for _ in range(3):
        base.click(*spot, bounds, fuzz=0.01)
        try:
            return base.wait_for(want, look=look, timeout=3, capture=False)
        except base.Lost:
            screen, _, _, bounds = look()
            if screen != then:
                break
    return base.wait_for(want, look=look, timeout=3)


def menu_tap(spot, bounds):
    """a tap in the BERRIES menu that shuts it: a berry, or above it"""
    return tap_to(spot, bounds, "feed", "berrymenu")


def choose():
    """on a gym Pokémon's page: the BERRIES menu, the first FEEDABLE kind with more than its floor picked
    -> (kind, its count), or None: none to spare (the menu shut again, out_of_berries set)"""
    global out_of_berries, razz_seen
    # the page opens on Razz. With the bag's Razz known (read in the menu earlier this run, less what was fed since)
    # and a magenta berry floating: no menu, 4.5 s saved per Pokémon. A Golden Razz is yellow
    _, texts, path, bounds = look()
    if razz_seen is not None and "RAZZ" not in spent and razz_seen > FEEDABLE["RAZZ"] and razz_up(path):
        return "RAZZ", razz_seen
    tap_to(BERRY_MENU, bounds, "berrymenu", "feed")
    seen = []
    while len(seen) < 2 or seen[-1] != seen[-2]:  # it slides up: two reads in a row must agree
        time.sleep(0.4)
        _, texts, path, bounds = look()
        menu = berry_menu(texts)
        seen.append({k: c for k, (c, _) in menu.items()})
        if len(seen) > 6:
            break
    menu = menu_counts(menu, texts, path)
    seen[-1] = {k: c for k, (c, _) in menu.items()}
    log("    bag: " + ", ".join(f"{k} {c}" for k, c in seen[-1].items()))
    razz_seen = seen[-1].get("RAZZ")
    for kind, floor in FEEDABLE.items():
        count, spot = menu.get(kind, (None, None))
        if count is not None and count > floor and kind not in spent:
            menu_tap(spot, bounds)
            time.sleep(0.8)  # the picked berry floats in
            return kind, count
    menu_tap(OFF_MENU, bounds)
    out_of_berries = True
    return None


def moved(screen, texts, me):
    """a page that reads as a gym Pokémon's, with another name than me's. The feeding can hide the name: not moved"""
    name, mine = (re.sub(r"\s", "", n.upper()) for n in (page_name(texts), me[0]))
    return screen == "feed" and name and not like(name, mine, 0.6)


def steady_look(me):
    """look(), again if the page seems to have changed: the stardust a berry gives floats over the name ('+10',
    'Scizor STARGUSTO') and goes in a moment. It stopped Blissey at 3 berries (2026-11-06). A real change stays"""
    got = look()
    for _ in range(4):
        if not moved(got[0], got[1], me):
            break
        time.sleep(0.7)
        got = look()
    return got


def berry_back(me):
    """no berry showing: look for FULL_WAIT s (it's gone while the last one is eaten, and floats in late on a page
    just opened) -> (a berry floats, the last look: screen, texts, path, bounds)"""
    end = time.time() + FULL_WAIT
    while True:
        time.sleep(0.6)
        screen, texts, path, bounds = look()
        up = screen == "feed" and berry_up(path)
        if up or time.time() >= end or moved(screen, texts, me):
            return up, screen, texts, path, bounds


def feed(kind, have, left, me):
    """on `me`'s page with `kind` picked (`have` in the bag): tap the berry while one floats, the bag keeps more than
    FEEDABLE[kind] and fewer than `left` are fed -> (berries fed, why it stopped: "full", "floor", "limit", "stuck" or
    "moved": another Pokémon's page). Each tap on a floating berry counts as one fed"""
    global razz_seen
    floor = FEEDABLE[kind]
    spare = min(have - floor, left)
    fed, start, why = 0, time.time(), "limit"
    while True:
        # a full Pokémon's berry can still show for a moment. A tap with no berry jumps to the faint Pokémon behind
        # (Blissey and Hitmonchan -> Greninja, 2026-11-06), so no tap before a look BERRY_WAIT after the last one
        screen, texts, path, bounds = steady_look(me)
        up = screen == "feed" and berry_up(path)
        if not up and not moved(screen, texts, me):
            up, screen, texts, path, bounds = berry_back(me)
        if moved(screen, texts, me):
            keep_capture(f"moved-{me[0]}")
            log(f"    the page changed from {me[0]} to {page_name(texts)}: stopping")
            why = "moved"
            break
        if not up:
            keep_capture(f"full-{me[0]}")
            why = "full"
            break
        if fed >= spare:
            break
        if fed >= MAX_TAPS:
            keep_capture("berrystuck")
            log(f"    {fed} taps and the berry still floats: moving on")
            why = "stuck"
            break
        base.click(*BERRY, bounds, fuzz=0.02)
        fed += 1
        time.sleep(BERRY_WAIT)
    if fed >= spare and why == "limit" and spare < left:
        why = "floor"
    if why == "floor":
        spent.add(kind)
    if kind == "RAZZ":
        razz_seen = have - fed
    log(f"    {kind}: {fed} taps in {time.time() - start:.0f}s, {why}")
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
    if not berry_up(path) and not berry_back(me)[0]:  # it floats in late
        keep_capture(f"full-{me[0]}")
        log(f"  {me[0]} ({me[1]}): full")
        return 0
    got = 0
    while total + got < limit:
        picked = choose()
        if not picked:
            log(f"  no berry to spare: every kind is down to what's kept ("
                + ", ".join(f"{k} {n}" for k, n in FEEDABLE.items()) + ")")
            break
        n, why = feed(*picked, limit - total - got, me)
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
        base.tap_x(look()[3], fuzz=0.006)  # one already fed: the tap went to the one in front
        _, _, _, bounds = base.wait_for("gymview", look=look, timeout=8)
        time.sleep(0.8)
    return None


def gym(total, limit):
    """in a gym's view: feed every Pokémon in it -> berries fed here"""
    known.clear()
    labels = sorted(all_labels(), key=lambda c: -c[0])
    _, _, _, bounds = look()
    log(f"  {len(labels)} CP labels in the gym view")
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
            base.tap_x(look()[3], fuzz=0.006)
            _, _, _, bounds = base.wait_for("gymview", look=look, timeout=8)
            time.sleep(0.8)
        if len(seen) >= GYM_SIZE or not missed:
            break
        todo = missed
    if len(seen) >= GYM_SIZE or total + fed >= limit or out_of_berries:
        return fed
    log(f"  {len(seen)} opened on a tap: looking for more by swiping")
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
    used = len(seen)
    fed += explore(seen, GYM_SIZE, total + fed, limit)
    log(f"  {len(seen) - used} more by swiping, {len(seen)} in all: " + ", ".join(k[0] for k in seen))
    base.tap_x(look()[3], fuzz=0.006)
    base.wait_for("gymview", look=look, timeout=8)
    return fed


def explore(seen, n, total, limit):
    """on a gym Pokémon's page: try SWIPES from each page reached until n are seen or nothing's left to try.
    -> berries fed. Each page is known by its name; a path of swipes leads back to one with swipes left"""
    edges, stays = {}, Counter()  # page -> {swipe: page it led to}; (page, swipe) -> times it stayed on that page
    here, fed, used = who(look()[1]), 0, 0
    while len(seen) < n and used < MAX_SWIPES and total + fed < limit and not out_of_berries:
        path = untried(edges, stays, here)[:1] or route(edges, stays, here)
        if not path:
            break
        for i in path:
            x1, y1, x2, y2 = SWIPES[i]
            _, _, _, bounds = look()
            base.drag(x1, y1, x2, y2, bounds, ms=150, settle=(0.7, 0.8))
            used += 1
            if not wait_feed(3):
                keep_capture("swipelost")
                raise Stop("a swipe in the gym left the Pokémon page")
            now = who(look()[1])
            log(f"    swipe {i} ({used}): {here[0]} -> {now[0]}")
            went = now != here
            if went:
                edges.setdefault(here, {})[i] = now
            else:
                stays[here, i] += 1
            if now not in seen:
                fed += feed_here(seen, total + fed, limit)
                now = who(look()[1])  # feeding can leave it on another page
            here = now
            if not went:
                break  # the rest of a path started from the page this one should have left
    return fed


def untried(edges, stays, page):
    """-> the swipes still to try from a page, the ones that stayed least first"""
    todo = [i for i in range(len(SWIPES)) if i not in edges.get(page, {}) and stays[page, i] < SWIPE_STAYS]
    return sorted(todo, key=lambda i: stays[page, i])


def route(edges, stays, start):
    """-> the swipes from start to the nearest page with an untried swipe (then that swipe), or None"""
    q, back = deque([start]), {start: None}
    while q:
        p = q.popleft()
        todo = untried(edges, stays, p)
        if todo and p != start:
            path = todo[:1]
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

feedable = None  # after a run: True, a gym is left to feed; False, none; None, not sure (timer left alone)


def script(limit):
    global feedable
    total, done, t0 = 0, set(), time.time()
    found, unsure = False, False  # a gym to feed seen; a gym that didn't open
    home.start(storage=False)
    while total < limit:
        fresh_list()
        sort_defending()
        got = pick(done)
        if not got:
            log("no gym of yours left that isn't gold")
            break
        name, (fx, fy), bounds = got
        done.add(name)
        base.click(fx, fy, bounds, fuzz=0.01)
        inside = into_gym()
        if inside == "none":
            log(f"{name}: no TIME DEFENDING, so no gym of yours is left")
            break
        found |= inside in ("gym", "raid")
        unsure |= inside == "shut"
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
    feedable = True if found else (None if unsure else False)
    log("gyms to feed: " + {True: "yes", False: "none", None: "not sure"}[feedable])
    log(f"done: {total} berries fed, {time.time() - t0:.0f}s")
    to_badge_list()  # out of the gym
    for _ in range(4):  # badge list -> profile -> map: the next script starts from the map
        screen, _, _, bounds = look()
        if screen not in ("badgelist", "profile"):
            break
        base.tap_x(bounds, fuzz=0.006)
        time.sleep(1.5)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--limit", type=int, default=LIMIT, help=f"at most N berries this run (default {LIMIT})")
    a = ap.parse_args()
    base.new_run_dir(os.path.join(HERE, "runs"), suffix=PHONE)
    try:
        session.main(script, a.limit)
    finally:  # after the phone is closed: turning the timer off can end the timer's own run
        if feedable is not None and os.access(TIMER, os.X_OK):
            subprocess.Popen([TIMER, "on" if feedable else "off"], start_new_session=True)


if __name__ == "__main__":
    main()
