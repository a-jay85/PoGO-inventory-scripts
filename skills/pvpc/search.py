#!/usr/bin/env python3
"""In-game searches and list walking, shared by /ivcsort and /pvpc's fallen-out step.

Types a search into the Pokémon list's search bar (start_search), reads every tile of the results
(run_search), or visits each tile once (walk_list). Tapping and timing come from run.py.
"""
import difflib, random, re, time
from collections import Counter
from PIL import Image

import ui
import run as base
from run import Stop, Skip, Lost, log, keep_capture, go, tap, wait_for, key, type_text, back_to_list, scroll, front

ZOOM = "/tmp/pvpc-zoom.png"
END_AFTER_STALE = 3
EXTRA_SCROLLS = 2  # a read short of the game's count scrolls this many more times before it gives up
MAX_SKIPS_IN_A_ROW = 5
# a new search typed over a scrolled list shows its results scrolled the same way, so the top rows are never read.
# Dragging back up isn't safe (one pull-down too many closes the Pokémon screen), so clear_search reopens it instead
scrolled = False


# ---------- walking a list ----------

def zoom_name(im, t):
    """read one tile's name again from a 3x crop under its CP: small names read better big ('od' -> '40 d')"""
    W, H = im.size
    cx, y = t[2], t[3]  # y: middle of the sprite; the name line is ~0.04 under it
    crop = im.crop((int((cx - 0.15) * W), int((y + 0.015) * H), int((cx + 0.15) * W), int((y + 0.07) * H)))
    crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS).save(ZOOM)
    got = [x[4] for x in ui.ocr(ZOOM) if re.search(r"\w", x[4])]
    return ui.tile_name(got[0]) if len(got) == 1 else None


def read_tiles(texts, path, odd=None):
    """the list's tiles with clean names. odd(name): names that don't look right get read again zoomed in"""
    out, im = [], None
    for n, c, x, y in ui.tiles(texts):
        n = ui.tile_name(n)
        if odd and odd(n):
            im = im or Image.open(path)
            z = zoom_name(im, (n, c, x, y))
            if z and not odd(z):
                log(f"  tile name {n!r} read again zoomed: {z!r}")
                n = z
        out.append((n, c, x, y))
    return out


def walk_list(visit, limit=10 ** 9, stop=None, odd=None):
    """call visit(i, name, cp) on each tile of the open list once, top to bottom. visit returns True if the tile
    left the list (so it isn't counted as passed). Ends after END_AFTER_STALE scrolls with nothing new.
    stop(name): the list is past what's wanted. odd: see read_tiles."""
    passed, seen = Counter(), set()
    stale, done, skips = 0, 0, 0
    full = None  # started on the full Pokémon list (start_search's results), not a tag's list
    while done < limit:
        _, texts, path, bounds = wait_for("list")
        if leave_multiselect(texts, bounds):  # a drag held too long at the list's end reads as a long press
            continue
        now_full = {"TAGS", "EGGS"} <= {ui.norm(t[4]) for t in texts}
        full = now_full if full is None else full
        if now_full and not full:  # a tag's list turned into the whole Pokémon list: it was closed
            raise Stop("left the tag's list (the full Pokémon list is showing)")
        ts = read_tiles(texts, path, odd)
        seen.update((t[0].upper(), t[1]) for t in ts)
        here, pick = Counter(), None
        for i, (n, c, _, _) in enumerate(ts, 1):
            here[(n, c)] += 1
            if here[(n, c)] > passed[(n, c)]:
                pick = (i, n, c)
                break
        if not pick:
            before = set(seen)
            global scrolled
            scrolled = True
            scroll(bounds, "drag")
            screen, texts, _, _ = wait_for("list", "detail")
            if screen == "detail":  # the drag landed as a tap and opened a tile: back out and drag again
                log("the scroll opened a Pokémon: backing out")
                back_to_list()
                continue
            if ui.ANDROID and not ui.android.NO_WINDOW and not {(ui.tile_name(t[0]).upper(), t[1]) for t in ui.tiles(texts)} - before:
                # a frozen scrcpy picture of a scrolled list looks like a live one: ask the phone itself
                ui.android.sharp("/tmp/pvpc_phone_list.png")
                if {(ui.tile_name(t[0]).upper(), t[1]) for t in ui.tiles(ui.ocr("/tmp/pvpc_phone_list.png"))} - before:
                    ui.android.restart()
                    continue
            stale = 0 if {(ui.tile_name(t[0]).upper(), t[1]) for t in ui.tiles(texts)} - before else stale + 1
            if stale >= END_AFTER_STALE:
                log("end of list")
                return
            continue
        i, n, c = pick
        if stop and stop(n):
            log(f"  {n!r}: past what's wanted, done with this list")
            return
        try:
            gone = visit(i, n, c)
            skips = 0
        except (Skip, Lost) as e:
            if isinstance(e, Lost):
                base.recover(e, f"{n} CP{c}")
            else:
                keep_capture(f"skip-{n}")
                log(f"SKIP {n} CP{c}: {e}")
            gone = False
            skips += 1
            if skips >= MAX_SKIPS_IN_A_ROW:
                raise Stop(f"{skips} skips in a row, something's off")
            back_to_list()
        if not gone:
            passed[(n, c)] += 1
        done += 1


def pokeball(path):
    """the red-over-white Poké Ball at the bottom middle of the map"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    red = [im.getpixel((int(fx * W), int(0.916 * H))) for fx in (0.47, 0.5, 0.53)]
    white = [im.getpixel((int(fx * W), int(0.94 * H))) for fx in (0.47, 0.53)]  # the middle can be the gray button (Pixel)
    return all(r > 200 and g < 110 and b < 120 for r, g, b in red) and all(min(p) > 225 for p in white)


def off_map():
    """a pull-down past the top of the list closes the Pokémon screen. From the map: Poké Ball, then POKÉMON."""
    for _ in range(2):
        path, bounds = ui.capture()
        texts = ui.ocr(path)
        words = {ui.norm(t[4]) for t in texts}
        if {"POKDEX", "POKMON", "ITEMS", "SHOP"} <= {w.replace("É", "") for w in words}:  # main menu
            t = next(t for t in texts if ui.norm(t[4]).replace("É", "") == "POKMON")
            fx, fy = t[0] + t[2] / 2, t[1] + 0.055  # the round button under the label
        elif len(texts) <= 10 and pokeball(path):  # the map
            fx, fy = 0.5, 0.928
        else:
            return
        log("on the map / main menu: opening the Pokémon list")
        click(fx + random.uniform(-0.01, 0.01), fy + random.uniform(-0.005, 0.005), bounds)
        time.sleep(random.uniform(1.5, 2.0))


def click(fx, fy, bounds, gap=0.0):
    """a tap at a spot (not a named button). It counts as a tap for the gap, so two quick taps on the search bar
    can't turn into a double-tap (that selects the text and the bar stops taking keys). gap: at least this long
    since the last tap."""
    front()
    x, y = base.to_points(fx, fy, bounds)
    base.tap_gap()
    time.sleep(max(0.0, base.last_tap + gap - time.time()))
    ui.sh(ui.HELPER, "click", f"{x:.1f}", f"{y:.1f}", str(random.randint(50, 100)))
    base.last_tap = time.time()


def leave_multiselect(texts, bounds):
    """a tap read as a long press puts the list in multi-select ('SELECT ALL', X top left), which hides the count.
    Tap the X. True if it was on."""
    sel = next((t for t in texts if t[1] > 0.7 and re.fullmatch(r"SELECT\s*\(\d+\)", t[4].strip().upper())), None)
    if sel:  # Android: a 'SELECT (1)' button near the bottom, with a round X under it
        log("the list went into multi-select: leaving it")
        click(0.5, sel[1] + sel[3] / 2 + 0.077, bounds)
        time.sleep(random.uniform(0.6, 0.8))
        return True
    if not any(t[1] < 0.15 and ui.norm(t[4]) == "SELECT ALL" for t in texts):
        return False
    x = next((t for t in texts if t[1] < 0.15 and t[4].strip() in ("X", "x", "×")), None)
    log("the list went into multi-select: leaving it")
    click(x[0] + x[2] / 2 if x else 0.123, x[1] + x[3] / 2 if x else 0.13, bounds)
    time.sleep(random.uniform(0.6, 0.8))
    return True


BAR_GAP = 0.7  # two taps on the bar closer than this act as a double-tap


def empty_bar(texts):
    """after the (x) clears it, the bar shows only the magnifier, or nothing past the < (no 'Search' word)"""
    bar = [t[4].strip() for t in texts if 0.15 < t[1] < 0.2]
    whole = any(t[1] < 0.15 and re.fullmatch(r"[\d,]+\s*/\s*[\d,]+", t[4].strip()) for t in texts)  # 'POKÉMON 7816/7825'
    return bool(bar) and all(b in ("Q", "9", "<", "‹", "< Q", "‹ Q", "< 9", "‹ 9") for b in bar) and (whole or "Q" in bar)


def open_panel(bounds):
    """tap the search bar. True if the panel opened with an empty bar"""
    click(random.uniform(0.35, 0.55), 0.183 + random.uniform(-0.003, 0.003), bounds, gap=BAR_GAP)
    for _ in range(10 if ui.ANDROID else 5):  # Android's keyboard can take over 1.5s to come up
        time.sleep(0.3)
        got, texts = panel_text()
        if ui.search_panel(texts):
            return not got
    return False


def to_search_list():
    """the full Pokémon list with its search bar: Tags tab, then the POKÉMON tab (switching tabs puts the list back at the top)"""
    path, bounds = ui.capture()
    texts = ui.ocr(path)
    if ui.search_panel(texts):  # a stop mid-search left the panel open
        box = ui.search_box(texts)
        if box and ui.search_text(box):
            close_panel(bounds)  # the (x) empties the bar and closes it
        else:  # an empty bar has no (x): the < back arrow
            click(0.10, 0.155, bounds)
            time.sleep(random.uniform(1.2, 1.5))
    if base.look()[0] == "tags":  # cut off with the tag sheet open
        if not any(base.tick_tags().values()):  # ticks half changed (IVC off, Nope not on yet): DONE would save that
            raise Stop("left on the tag sheet with nothing ticked: finish this Pokémon by hand")
        go("DONE", "detail")
    if base.look()[0] in ("detail", "menu", "appraisal"):  # left on a Pokémon (a stop mid-visit): back out first
        back_to_list()
    off_map()
    base.to_tags_tab()
    for _ in range(3):
        time.sleep(random.uniform(0.8, 1.0))  # a tab tap during the tab animation gets ignored
        go("POKMON", "list")
        _, texts, _, bounds = wait_for("list")
        if ui.search_box(texts) or empty_bar(texts):
            global scrolled
            scrolled = False
            break
        log("  no search bar yet: tapping POKÉMON again")
    else:
        keep_capture("nosearch")
        raise Stop("no search bar on the Pokémon list")


def search_screen():
    """after a search the list can be short (no 'Search' word, under 6 CPs): any screen with the typed query on top"""
    for _ in range(40):
        path, bounds = ui.capture()
        texts = ui.ocr(path)
        box = ui.search_box(texts)
        if box is not None and ui.search_text(box).strip().upper() not in ("", "SEARCH"):
            return texts, bounds
        time.sleep(0.15)
    keep_capture("search")
    raise Stop("typed query never showed in the search bar")


def same_query(got, want):
    """OCR of the search bar vs what was typed. OCR can drop or swap a symbol, but a leftover old query makes it much longer."""
    want = want.lower()
    a = re.sub(r"\s", "", got or "").lower()
    ends = [want]
    if len(want) > 22 and 12 <= len(a) < len(want):  # a long search doesn't fit in the bar: only its end shows
        ends = [want[-len(a):], want[:len(a)]]  # (Android shows its start once Return is pressed)
    for a in (a, a[1:] if a.startswith("9") else a):  # the magnifier read as a 9
        for b in ends:
            if difflib.SequenceMatcher(None, a, b).ratio() >= 0.8 and abs(len(a) - len(b)) <= 2 \
                    and re.sub(r"\D", "", a) == re.sub(r"\D", "", b):  # symbols can misread, dex numbers can't
                return True
    return False


def x_button(bounds):
    """the (x) at the right end of a typed search bar empties it (much quicker than closing the list).
    Then a tap on the bar opens the panel. True if it's open and empty."""
    click(0.905 + random.uniform(-0.006, 0.006), 0.183 + random.uniform(-0.003, 0.003), bounds, gap=BAR_GAP)
    for _ in range(12):  # the whole list reloads: a tap on the bar before it's back gets ignored
        time.sleep(0.25)
        texts = ui.ocr(ui.capture()[0])
        if any(t[1] < 0.15 and re.fullmatch(r"[\d,]+\s*/\s*[\d,]+", t[4].strip()) for t in texts):
            break  # 'POKÉMON 7816/7825' is back
    for _ in range(2):
        if open_panel(bounds):
            return True
    return False


def clear_search():
    """typing only lands in an empty search bar, and the game empties it when the Pokémon screen reopens:
    close it with the X at the bottom, then Poké Ball -> POKÉMON. A scrolled list always goes that way: it reopens at the top"""
    global scrolled
    for _ in range(3):
        path, bounds = ui.capture()
        texts = ui.ocr(path)
        if leave_multiselect(texts, bounds):
            continue
        if ui.search_panel(texts):  # left open: a Return that didn't take
            box = ui.search_box(texts)
            if not (box and ui.search_text(box)):
                if not scrolled:
                    return "panel"  # open and empty: ready to type
                click(0.10, 0.155, bounds)  # the < back arrow, then reopen below
                time.sleep(random.uniform(1.2, 1.5))
            else:
                close_panel(bounds)
        try:
            screen, texts, _, bounds = wait_for("list", "tag-tab", "detail", "menu", "appraisal", timeout=6)
        except Stop:
            if not ui.ANDROID:
                raise
            for _ in range(4):  # a panel that took its time to open
                got, texts = panel_text()
                if ui.search_panel(texts):
                    break
                time.sleep(0.5)
            else:
                raise
            if not got:
                return "panel"
            continue
        if screen == "list" and ui.search_box(texts) and not ui.search_text(ui.search_box(texts)):
            return "list"
        if screen == "list" and not scrolled and ui.search_box(texts) and x_button(bounds):
            return "panel"
        if screen == "list" and not scrolled and empty_bar(texts) and open_panel(bounds):
            return "panel"
        if screen not in ("list", "tag-tab"):
            back_to_list()
            screen, texts, _, bounds = wait_for("list", "tag-tab")
        click(0.5 + random.uniform(-0.01, 0.01), 0.93 + random.uniform(-0.004, 0.004), bounds)
        time.sleep(random.uniform(1.6, 2.0))
        off_map()
        scrolled = False
    keep_capture("clear")
    raise Stop("couldn't get an empty search bar")


def result_count(texts):
    """the 'Q (7)' under the POKÉMON tab after a search"""
    for t in texts:
        m = re.match(r"[Q9]?\s*\((\d[\d,]*)\)", t[4])  # the Q icon can read as 9
        if t[1] < 0.15 and m:
            return int(m.group(1).replace(",", ""))


def panel_text():
    texts = ui.ocr(ui.capture()[0])
    box = ui.search_box(texts)
    return (ui.search_text(box) if box else ""), texts


def bar_shows(got, q):
    """same_query, and on Android a second look: the normal-size picture loses small symbols ('!', '&'), so read the
    bar off the phone's own screenshot at 3x"""
    if same_query(got, q):
        return True
    if ui.ANDROID:
        box = ui.search_box(ui.ocr(ui.android.sharp()))
        return bool(box) and same_query(ui.search_text(box), q)
    return False


def type_into_panel(q, bounds):
    """the panel doesn't always put the cursor in the bar, and a tap on the bar doesn't always either.
    Tap the bar, type, wait for the letters to show. False if they come out wrong (the caller starts over)."""
    for attempt in range(4):
        if attempt:  # the tap that opened the panel already put the cursor in the bar: a 2nd tap can lose it
            click(random.uniform(0.35, 0.55), 0.183 + random.uniform(-0.003, 0.003), bounds, gap=BAR_GAP)
        time.sleep(random.uniform(0.4, 0.5))
        if not ui.ANDROID:  # adb's input text never drops a shift
            type_text("A")  # the first shifted keys after the tap lose their shift ('#IVC' -> '3iVC'): wake it up
            time.sleep(0.15)
            key("delete")
            time.sleep(0.15)
        type_text(q)
        got = ""
        for i in range(16):
            time.sleep(0.25)
            got, _ = panel_text()
            if not got and i >= 4:
                log("  nothing showed in the search bar after typing: again")
                break  # nothing landed: tap and type again
            if got and not (len(got) < len(q) and q.lower().startswith(re.sub(r"\s", "", got).lower())):
                break  # the keys can land a little after they're sent: wait while only the start shows
        if got:
            if bar_shows(got, q):
                return True
            log(f"search bar says {got!r}, wanted {q!r}")
            return False
    return False


def close_panel(bounds):
    """the panel's (x) empties the bar and closes the panel"""
    click(0.905 + random.uniform(-0.006, 0.006), 0.183 + random.uniform(-0.003, 0.003), bounds, gap=BAR_GAP)
    time.sleep(random.uniform(1.2, 1.5))


def hp_bar(im, t):
    """the coloured HP bar right under a tile's name"""
    W, H = im.size
    cx = t[0] + t[2] / 2
    for dy in (0.004, 0.007, 0.010, 0.013):
        px = [im.getpixel((int((cx + dx) * W), int((t[1] + t[3] + dy) * H))) for dx in (-0.03, 0, 0.03)]
        if all(max(p) - min(p) > 50 and max(p) > 150 for p in px):
            return True
    return False


def top_row(path, texts):
    """a chip row ('#Luckydex +') can hide the top row's CPs under the search bar: read those names off their HP bars.
    Only on the first screen, so a row that scrolled up under the bar isn't counted twice."""
    cps = [t for t in texts if re.fullmatch(r"CP\s*\d+", t[4].upper().replace(" ", ""))]
    first_cp = min((c[1] for c in cps), default=1.0)
    head = max((t[1] + t[3] for t in texts if t[1] < 0.35 and (ui.norm(t[4]) == "SHOW EVOLUTIONARY LINE" or ui.search_box([t]))), default=0.2)
    im = Image.open(path).convert("RGB")
    out = []
    for t in texts:
        if head < t[1] < first_cp + 0.05 and not re.fullmatch(r"CP\s*\d+", t[4].upper().replace(" ", "")) and hp_bar(im, t):
            if not any(0 < t[1] - c[1] < 0.13 and abs((t[0] + t[2] / 2) - (c[0] + c[2] / 2)) < 0.1 for c in cps):
                out.append((ui.tile_name(t[4]), 0))
    return out


def small_scroll(bounds):
    """about a row and a half, so every tile is read on two or three screens"""
    global scrolled
    scrolled = True
    front()
    fx, fy = random.uniform(0.3, 0.7), random.uniform(0.6, 0.7)
    x, y = base.to_points(fx, fy, bounds)
    # an adb swipe flings on: 0.22 in 550ms moved 0.25-0.30, and rows slipped past between two looks.
    # Slower and shorter lands near 0.22 (measured on the Pixel, 2026-10-09)
    dist = bounds[3] * (random.uniform(0.17, 0.19) if ui.ANDROID else random.uniform(0.2, 0.25))
    ms = random.randint(900, 1100) if ui.ANDROID else random.randint(450, 650)
    ui.sh(ui.HELPER, "drag", f"{x:.1f}", f"{y:.1f}", f"{x + random.uniform(-6, 6):.1f}", f"{y - dist:.1f}", str(ms))
    time.sleep(random.uniform(0.7, 0.9))


def merge_cutoffs(most, sightings):
    """a name read while half hidden (under the X button or the edge) comes out short: 'Cha' for 'Charmander',
    '96' for '96 AD'. Same CP and the start of a longer name: fold it into the longer one."""
    for k in sorted(most, key=lambda k: len(k[0])):
        longer = [o for o in most if o != k and o[1] == k[1] and len(o[0]) > len(k[0]) and o[0].startswith(k[0])]
        if longer:
            o = max(longer, key=lambda o: sightings[o])
            most[o] = max(most[o], most[k])
            sightings[o] += sightings[k]
            del most[k]


def drop_misreads(most, sightings, extra):
    """more tiles than the game counts: a CP read wrong once makes a twin of a real tile.
    Drop the twins seen on the fewest screens whose name matches a tile with a CP one digit away."""
    def near(a, b):
        a, b = str(a), str(b)
        return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1
    twins = sorted((sightings[k], k) for k in most
                   if any(o != k and o[0] == k[0] and near(o[1], k[1]) and sightings[o] > sightings[k] for o in most))
    for _, k in twins[:extra]:
        log(f"  dropping {k}: looks like a misread twin")
        most[k] -= 1
        if most[k] <= 0:
            del most[k]


def start_search(q):
    """type one search (Return, SHOW EVOLUTIONARY LINE unticked). -> (path, texts, bounds) of the results, at the top"""
    t0 = time.time()
    for attempt in range(3):
        c = clear_search()
        t1 = time.time()
        if c == "list":
            tap("search")
            time.sleep(random.uniform(1.0, 1.3))  # the panel comes up
        path, bounds = ui.capture()
        if not ui.search_panel(ui.ocr(path)):
            log("search panel didn't open")
            continue
        if not type_into_panel(q, bounds):
            continue
        key("return")
        for _ in range(12):  # the panel closes and the results show
            time.sleep(0.25)
            got, texts = panel_text()
            if not ui.search_panel(texts) and ui.classify(texts) == "list":
                break
        else:
            log("the panel didn't close after Return")
            continue
        if bar_shows(got, q):
            if not {"TAGS", "EGGS"} <= {ui.norm(t[4]) for t in texts}:  # typed in a tag's list: only searched that tag
                log("  that searched inside a tag's list: going to the full Pokémon list")
                to_search_list()
                continue
            log(f"  timing: clear {t1 - t0:.1f}s, type {time.time() - t1:.1f}s ({c})")
            break
        log(f"search bar says {got!r}, wanted {q!r}: typing it again")
    else:
        keep_capture("search")
        raise Stop(f"search bar never showed {q!r}")
    for _ in range(3):  # SHOW EVOLUTIONARY LINE would pull in the whole family
        path, bounds = ui.capture()
        texts = ui.ocr(path)
        ticked = ui.evo_ticked(path, texts)
        if not ticked:
            break
        log("SHOW EVOLUTIONARY LINE is ticked: unticking it")
        tap("EVOLINE")
        time.sleep(random.uniform(1.0, 1.4))
    else:
        keep_capture("evoline")
        raise Stop("SHOW EVOLUTIONARY LINE stays ticked")
    if ticked is None:
        log("can't see SHOW EVOLUTIONARY LINE after the search")
    return path, texts, bounds


def run_search(q, iv_only=False):
    """type one search, read every tile. -> [(name, cp)], duplicates counted by the most seen on one screen.
    iv_only: the list is sorted by name, so IV names ('96 HA') come first: stop at the plain names. The count
    can't be checked then, so want comes back None."""
    path, texts, bounds = start_search(q)
    if leave_multiselect(texts, bounds):
        path, bounds = ui.capture()
        texts = ui.ocr(path)
    want = result_count(texts)
    if want == 0:
        return [], 0
    most, sightings, seen, stale, stuck, last = Counter(), Counter(), set(), 0, 0, None
    for turn in range(300):
        now = Counter((ui.tile_name(t[0]), t[1]) for t in ui.tiles(texts))
        if turn == 0:
            now.update(top_row(path, texts))
        for k, v in now.items():
            most[k] = max(most[k], v)
            sightings[k] += 1
        if want is not None and want <= 9 and sum(most.values()) == want:  # one screen, all read
            break
        order = [bool(re.match(r"\d", ui.tile_name(t[0]))) for t in ui.tiles(texts)]  # row by row
        if iv_only and order.count(False) >= 3:  # past the IV names
            if True in order[order.index(False):]:  # an IV name after a plain one: not sorted by name
                log(f"  {q}: the list isn't sorted by Name (IV names after plain ones): reading all of it")
                iv_only = False
            else:
                if want is not None and sum(most.values()) < want:
                    want = None
                break
        if want is None and len(now) < 9:  # under three rows: everything is on screen
            break
        short = want is not None and sum(most.values()) < want  # the game counted more than we've read
        stuck = stuck + 1 if now == last else 0
        if stuck > (EXTRA_SCROLLS if short else 0):  # the list didn't move: the end (a short read scrolls again first)
            break
        last = now
        fresh = set(now) - seen
        seen |= set(now)
        stale = 0 if fresh else stale + 1
        if stale >= END_AFTER_STALE + (EXTRA_SCROLLS if short else 0):
            break
        small_scroll(bounds)
        path, bounds = ui.capture()  # the search bar may have scrolled away: just read the tiles
        texts = ui.ocr(path)
    merge_cutoffs(most, sightings)
    if want is not None and sum(most.values()) > want:
        drop_misreads(most, sightings, sum(most.values()) - want)
    got = [k for k, v in most.items() for _ in range(v)]
    if want is not None and len(got) != want:
        log(f"  {q}: read {len(got)} tiles, the game says {want}")
    return got, want


def looks_same(a, b):
    """'98 AD BS*' and '98 ADBS V': one name OCR'd two ways. '96 ATK' and '96 HA' are two Pokémon."""
    a, b = (re.sub(r"[^a-z0-9]", "", x.lower()) for x in (a, b))
    return abs(len(a) - len(b)) <= 1 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


