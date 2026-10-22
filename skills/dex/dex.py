#!/usr/bin/env python3
"""/dex: read one Pokédex page and print a storage search of the Pokémon missing from it, for another account
to paste. Android only for now.

  POGO_PHONE=android caffeinate -dimsu python3 dex.py lucky     the Lucky page
  POGO_PHONE=android caffeinate -dimsu python3 dex.py 100       the ★100% page
  POGO_PHONE=android python3 dex.py look                        what it reads on a grid screen now; taps nothing

Gets there from anywhere: main menu, POKÉDEX, the page's chip at the bottom, then KANTO. The page is one long grid,
four to a row, Kanto to Paldea (0001-1024). A caught entry has a picture with its number at the bottom of the tile.
A missing one is an empty tile with its number in the middle. The script scrolls the grid top to bottom and reads
every number by OCR. It checks that each screen shares a number with the one before (no rows skipped), and that
the caught count matches the page's "Caught:" total, before it prints anything.

Missing numbers become a dex-number search with ranges (`14,22,29-33`). A long list is split into several searches
of at most MAX_CHARS characters. Log and searches go in runs/<time>-<page>/.
"""
import argparse, os, random, re, statistics, sys, time
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, log, keep_capture
import home, search

PAGES = {"lucky": "LUCKY", "100": "100%"}  # page -> its chip's label
MAX_CHARS = 1000  # per search. The Pixel's search bar took 1,397 characters and failed at 1,497 (2026-10-21)
CHIP_Y = 0.845  # the chip row's labels (POKÉMON, SHINY, LUCKY ... ★100%)
HEADER_SMALL = 0.13  # bottom of the region header while the grid is scrolled (KANTO 120)
HEADER_BIG = 0.215  # ...and with "Recently registered" (top and bottom of the grid)
ABOVE = (0.085, 0.012)  # the box looked at above a number: from this far above it to this far above
MIN_BOX = 0.04  # ...cut at the header, but at least this tall (a missing #1's number is close under the header)
HALF_W = 0.07  # ...this wide either side of the number's middle (the up/down button sits at the right edge)
# brightness spread in that box: empty tiles read 2-10, pictures 13-50 (a faint Togetic: 12.8)
SURE_PIC, SURE_PLAIN = 20, 5  # a tile this busy or this plain pins down the row heights
BUSY_MIN, PLAIN_MAX = 17, 8  # with no heights to measure against, only a spread this clear decides
DROP = 0.047  # a missing tile's number sits this much higher than a caught one's in the same row
PITCH = 0.1415  # rows are this far apart
TITLE_GAP = 0.137  # a region's title sits this far above the caught height of the first row under it
FIT = 0.015  # a number this close to a row height sits at it
SCROLL = 0.25  # of the screen per swipe, ~1.7 rows: the clear band shows ~4.5, so each screen repeats ~2 rows
MAX_SCREENS = 400
# not on the Lucky or the 100% page at all: the species that can't be traded (Mew, Celebi, Jirachi, Deoxys,
# Phione to Arceus, the Unova and Kalos mythicals, Zygarde, Magearna, Marshadow, Zeraora, Meltan, Melmetal, Zarude)
NOT_LISTED = {151, 251, 385, 386, *range(489, 495), 647, 648, 649, *range(718, 722), 801, 802, 807, 808, 809, 893}


# ---------- reading ----------

def joined(texts):
    return " ".join(t[4].upper() for t in texts)


def numbers(texts):
    """the 4-digit Pokédex numbers on screen -> [(n, text box)]"""
    out = []
    for t in texts:
        s = t[4].replace("O", "0").replace("o", "0").strip()
        if re.fullmatch(r"\d{4}", s) and int(s) > 0:
            out.append((int(s), t))
    return out


def band(texts):
    """the part of the grid nothing covers -> (top, bottom). The region header grows at the top and bottom of the
    grid, and the chips sit over the bottom rows."""
    top = HEADER_BIG if "RECENTLY" in joined(texts) else HEADER_SMALL
    chips = [t[1] for t in texts if t[1] > 0.78 and re.search(r"SHINY|LUCKY|XXL|XXS|SHADOW|PURIFIED|100%|POK",
                                                              t[4].upper())]
    return top, (min(chips) if chips else CHIP_Y) - 0.025


def spread(im, t, top):
    """how busy the tile is just above its number: a picture, or plain tile. The box stops at the header (top)."""
    W, H = im.size
    cx, y = t[0] + t[2] / 2, t[1]
    box = im.crop((int((cx - HALF_W) * W), int(max(y - ABOVE[0], top) * H), int((cx + HALF_W) * W),
                   int((y - ABOVE[1]) * H)))
    return statistics.pstdev(box.convert("L").getdata())


def read_grid(path, texts):
    """-> ({n: True if missing}, [(n, y, spread, missing)] for the log). Raises Stop when it can't tell.

    The number's height decides. Rows are PITCH apart, a caught number at the bottom of its tile and a missing one
    DROP higher. The sure tiles on the screen pin those heights down: a busy picture (caught), a plain tile (missing),
    any row with numbers at two heights (the lower ones caught), and a region's title. The spread backs it up."""
    im = Image.open(path).convert("RGB")
    top, bottom = band(texts)
    tiles = []
    for n, t in numbers(texts):
        if t[1] - ABOVE[1] - MIN_BOX < top or t[1] + t[3] > bottom:
            continue  # under the header or the chips: the next screen has it whole
        tiles.append((n, t[1], spread(im, t, top)))
    tiles.sort(key=lambda r: r[1])
    # a region's title (SINNOH) between two regions starts a new grid: heights only carry within one part
    titles = sorted(t[1] for t in texts if top < t[1] < bottom and re.fullmatch(r"[A-Z]{4,}", t[4].strip()))
    part = lambda y: sum(ty < y for ty in titles)
    refs = [(part(ty + 0.01), ty + TITLE_GAP) for ty in titles]  # (part, height a caught number would sit at)
    for n, y, s in tiles:
        if s >= SURE_PIC:
            refs.append((part(y), y))
        elif s <= SURE_PLAIN:
            refs.append((part(y), y + DROP))
    for n, y, s in tiles:  # a row with two heights: the lower numbers are caught
        mates = [m[1] for m in tiles if abs(m[1] - y) < DROP + 0.02 and part(m[1]) == part(y)]
        if max(mates) - min(mates) > DROP / 2 and y - min(mates) > DROP / 2:
            refs.append((part(y), y))
    rows = []
    for n, y, s in tiles:
        missing = None
        mine = [r for p, r in refs if p == part(y)]
        if mine:
            r = min(mine, key=lambda r: abs(r - y))
            off = lambda v: abs(v - r - round((v - r) / PITCH) * PITCH)
            if off(y) < FIT and off(y + DROP) > 2 * FIT:
                missing = False
            elif off(y + DROP) < FIT and off(y) > 2 * FIT:
                missing = True
        if missing is None:  # nothing to measure against: the spread alone, if it's clear
            if s >= BUSY_MIN:
                missing = False
            elif s <= PLAIN_MAX:
                missing = True
            else:
                raise Stop(f"can't tell #{n} (height {y:.3f}, spread {s:.1f}): {tiles}")
        if (missing and s >= BUSY_MIN) or (not missing and s <= SURE_PLAIN):
            raise Stop(f"#{n} sits like a {'missing' if missing else 'caught'} one but its spread is {s:.1f}: {tiles}")
        rows.append((n, y, s, missing))
    return {r[0]: r[3] for r in rows}, rows


# ---------- getting there ----------

def where(path, texts):
    j = joined(texts)
    if numbers(texts) and "REGIONS" in j:
        return "grid"
    if "FILTER BY" in j:
        return "dex-search"
    if "POK" in j and any(t[1] < 0.1 and t[4].upper().startswith("CAUGHT") for t in texts) and "KANTO" in j:
        return "regions"
    return home.where(path, texts)


def look():
    path, bounds = ui.capture()
    texts = ui.ocr(path)
    ui.remember(path, texts, bounds)
    return where(path, texts), texts, path, bounds


def tap_at(fx, fy, bounds, wait=(1.6, 2.2)):
    search.click(fx + random.uniform(-0.006, 0.006), fy + random.uniform(-0.003, 0.003), bounds)
    time.sleep(random.uniform(*wait))


def tap_text(texts, bounds, pred, dy=0.0):
    t = next((t for t in texts if pred(t)), None)
    if not t:
        return False
    tap_at(t[0] + t[2] / 2, t[1] + t[3] / 2 + dy, bounds)
    return True


def swipe(fx1, fy1, fx2, fy2, bounds):
    x1, y1 = base.to_points(fx1, fy1, bounds)
    x2, y2 = base.to_points(fx2, fy2, bounds)
    ui.sh(ui.HELPER, "drag", f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}", str(random.randint(450, 600)))
    time.sleep(random.uniform(0.8, 1.1))


def to_regions():
    """from anywhere to the Pokédex's region list"""
    home.start(storage=False)
    for _ in range(15):
        screen, texts, path, bounds = look()
        if screen == "regions":
            return texts, bounds
        if screen in ("grid", "dex-search", "list", "tag-tab"):
            ui.android.key("back")
            time.sleep(1.5)
        elif screen in home.OPEN:
            base.back_to_list()
        elif screen == "mainmenu":
            log("main menu: opening the Pokédex")
            tap_text(texts, bounds, lambda t: ui.norm(t[4]).replace("É", "") == "POKDEX", dy=0.055)
        elif screen == "map":
            log("map: opening the main menu")
            tap_at(0.5, 0.928, bounds)
        elif screen == "exit":
            home.press_text(texts, bounds, "CANCEL")
            time.sleep(1.5)
        else:
            home.unstick(texts)
    keep_capture("regions")
    raise Stop("couldn't get to the Pokédex")


def chip(texts, label):
    return next((t for t in texts if t[1] > 0.78 and label in t[4].upper().replace(" ", "")), None)


def chip_on(path, t):
    """a picked chip is filled with the page's colour; the others are white"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    r, g, b = im.getpixel((int((t[0] - 0.02) * W), int((t[1] + t[3] / 2) * H)))
    return min(r, g, b) < 200


def pick_page(label):
    """tap the page's chip (swiping the chip row until it shows) -> the page's Caught total"""
    swipes = [(0.85, 0.15)] * 3 + [(0.15, 0.85)] * 6  # toward the end of the row first, then back
    for i in range(len(swipes) + 1):
        screen, texts, path, bounds = look()
        if screen != "regions":
            raise Stop(f"left the Pokédex's region list ({screen})")
        t = chip(texts, label)
        if t and chip_on(path, t):
            m = next((re.search(r"(\d[\d,]*)", t2[4]) for t2 in texts
                      if t2[1] < 0.1 and t2[4].upper().startswith("CAUGHT")), None)
            if not m:
                raise Stop("can't read the page's Caught total")
            return int(m.group(1).replace(",", "")), texts, bounds
        if t:
            log(f"tapping the {label} chip")
            tap_at(t[0] + t[2] / 2, t[1] + t[3] / 2, bounds)
            continue
        if i == len(swipes):
            break
        a, b = swipes[i]
        swipe(a, CHIP_Y + 0.01, b, CHIP_Y + 0.01, bounds)
    keep_capture("chip")
    raise Stop(f"couldn't find the {label} chip")


# ---------- the grid ----------

def walk_grid():
    """from KANTO's grid at the top, scroll to the end -> {n: missing}"""
    seen, last_max, still = {}, None, 0
    edge = [0.0, 999.0]  # busiest missing tile, plainest caught one: how close the spread alone came to a wrong call
    for i in range(MAX_SCREENS):
        screen, texts, path, bounds = look()
        if screen != "grid":
            keep_capture("grid")
            raise Stop(f"not on the Pokédex grid any more ({screen})")
        got, rows = read_grid(path, texts)
        # skipped numbers a row or more in from the edges (an edge row can be half in: missing numbers sit higher)
        holes = lambda: [n for n in range(min(got) + 4, max(got) - 3) if n not in got and n not in NOT_LISTED] \
            if got else []
        if holes():  # the OCR skipped a number: read the phone's own screenshot at 3x
            log(f"  didn't read {holes()}: reading a sharper screenshot")
            got, rows = read_grid(path, ui.ocr(ui.android.sharp()))
            if holes():
                keep_capture("holes")
                raise Stop(f"can't read {holes()} on this screen")
        if not got:
            keep_capture("grid")
            raise Stop("read no numbers on this screen")
        if i == 0 and 1 not in got:
            keep_capture("grid")
            raise Stop(f"the grid didn't open at #1 (first number read: {min(got)})")
        clash = [n for n in got if n in seen and seen[n] != got[n]]
        if clash:
            keep_capture("clash")
            raise Stop(f"read these both ways on two screens: {clash}")
        if seen and not set(got) & set(seen):
            keep_capture("gap")
            raise Stop(f"this screen shares no number with the last one: rows may be skipped ({min(got)}-{max(got)})")
        new = sorted(n for n in got if n not in seen)
        for n, y, s, m in rows:
            edge[0 if m else 1] = max(edge[0], s) if m else min(edge[1], s)
        seen.update(got)
        if new:
            log(f"  {new[0]:4}-{new[-1]:4}: missing {[n for n in new if got[n]] or 'none'}")
        top = max(got)
        still = still + 1 if top == last_max else 0
        if still >= 2:
            log(f"spread: busiest missing tile {edge[0]:.1f}, plainest caught one {edge[1]:.1f} (sure at {SURE_PIC} and {SURE_PLAIN})")
            return seen
        last_max = top
        x, y = random.uniform(0.3, 0.7), random.uniform(0.6, 0.66)
        swipe(x, y, x + random.uniform(-0.02, 0.02), y - SCROLL, bounds)
    raise Stop(f"still scrolling after {MAX_SCREENS} screens")


# ---------- the search ----------

def ranges(ns):
    out, ns = [], sorted(ns)
    i = 0
    while i < len(ns):
        j = i
        while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
            j += 1
        out.append(str(ns[i]) if i == j else f"{ns[i]}-{ns[j]}")
        i = j + 1
    return out


def searches(ns):
    """comma lists of at most MAX_CHARS characters"""
    out, cur = [], ""
    for r in ranges(ns):
        if cur and len(cur) + 1 + len(r) > MAX_CHARS:
            out.append(cur)
            cur = ""
        cur = f"{cur},{r}" if cur else r
    return out + [cur] if cur else out


def run_page(page):
    label = PAGES[page]
    texts, bounds = to_regions()
    total, texts, bounds = pick_page(label)
    log(f"{label} page: {total} caught")
    if not tap_text(texts, bounds, lambda t: t[4].upper().strip() == "KANTO"):
        swipe(0.5, 0.3, 0.5, 0.75, bounds)  # region list scrolled down: back to the top
        screen, texts, path, bounds = look()
        if not tap_text(texts, bounds, lambda t: t[4].upper().strip() == "KANTO"):
            keep_capture("kanto")
            raise Stop("can't find KANTO on the region list")
    seen = walk_grid()
    missing = sorted(n for n, m in seen.items() if m)
    caught = len(seen) - len(missing)
    gaps = sorted(set(range(1, max(seen) + 1)) - set(seen))
    log(f"read #1-#{max(seen)}: {caught} caught, {len(missing)} missing"
        + (f", not on this page: {','.join(ranges(gaps))}" if gaps else ""))
    if caught != total:
        raise Stop(f"read {caught} caught but the page says {total}: not printing a search")
    if set(gaps) - NOT_LISTED:
        raise Stop(f"never read {ranges(set(gaps) - NOT_LISTED)}: not printing a search")
    out = searches(missing)
    with open(os.path.join(base.RUN_DIR, f"missing-{page}.txt"), "w") as f:
        f.write("\n\n".join(out) + "\n")
    print(f"\nMissing from the {label} page: {len(missing)} Pokémon, {len(out)} search(es)\n")
    for i, s in enumerate(out, 1):
        print(f"--- search {i} of {len(out)} ({len(s)} characters) ---\n{s}\n")
    print(f"saved to {os.path.join(base.RUN_DIR, f'missing-{page}.txt')}")


def cmd_look():
    screen, texts, path, bounds = look()
    print(f"screen: {screen}, band {band(texts)}")
    if screen == "grid":
        got, rows = read_grid(path, texts)
        for n, y, s, m in rows:
            print(f"  #{n:4}  y {y:.3f}  spread {s:5.1f}  {'MISSING' if m else 'caught'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page", choices=(*PAGES, "look"))
    a = ap.parse_args()
    if not ui.ANDROID:
        sys.exit("Android only for now: POGO_PHONE=android")
    try:
        if a.page == "look":
            cmd_look()
            return
        base.new_run_dir(None, os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S") + "-" + a.page))
        run_page(a.page)
    except Stop as e:
        log(f"STOPPED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
