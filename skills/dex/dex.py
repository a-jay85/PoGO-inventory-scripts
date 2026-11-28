#!/usr/bin/env python3
"""/dex: read one Pokédex page and print a storage search of the Pokémon missing from it, for another account
to paste. Android only for now.

  POGO_PHONE=android caffeinate -dimsu python3 dex.py lucky     the Lucky page
  POGO_PHONE=android caffeinate -dimsu python3 dex.py 100       the ★100% page
  POGO_PHONE=android caffeinate -dimsu python3 dex.py xxs       the XXS page: each search starts with xxs&
  POGO_PHONE=android python3 dex.py look                        what it reads on a grid screen now; taps nothing
  POGO_PHONE=android python3 dex.py evolve [lucky|xxs|100] [run]  the evolve step again on a page already read (default:
                                                                Lucky, its newest run); doesn't read the page again.
                                                                100: counts the 100s in storage again

Gets there from anywhere: main menu, POKÉDEX, the page's chip at the bottom, then KANTO. The page is one long grid,
four to a row, Kanto to Paldea (0001-1024). A caught entry has a picture with its number at the bottom of the tile.
A missing one is an empty tile with its number in the middle. The script scrolls the grid top to bottom and reads
every number by OCR. It checks that each screen shares a number with the one before (no rows skipped), and that
the caught count matches the page's "Caught:" total, before it prints anything.

Missing numbers become a dex-number search with ranges (`14,22,29-33`). A long list is split into several searches
of at most MAX_CHARS characters. Log and searches go in runs/<time>-<page>/.

A run takes about 5 minutes and only taps to move around: it never changes anything in the game.
The whole-search limit (MAX_CHARS): the Pixel's bar took 1,397 characters and failed at 1,497 (2026-10-21).
Each run saves the signed-in trainer to trainer.txt. Other scripts pick a run with dex.latest(page, trainer). Be on the
same account for evolve. Any check that fails stops the run with no search printed.
The Lucky and XXS runs also list the lucky or XXS ones in storage that could evolve into a hole (evolve-<page>.txt), and
leave those holes out of the search. Both keep their mark when they evolve, so one step (evolvable) does both.
The ★100% run counts the 100s in storage of each species on the page with a missing evolution (count_owned, counts
only, owned-100.json): the page shows one was there once, not that it still is. hundred_useful works from both.
"""
import argparse, difflib, os, random, re, statistics, sys, time
from PIL import Image

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log, keep_capture
import home, pvp, search, session, tagsheet

PAGES = {"lucky": "LUCKY", "100": "100%", "xxs": "XXS"}  # page -> its chip's label
PREFIX = {"xxs": "xxs&"}  # once in front of each search: OR binds tighter, so xxs&1-3,7 is xxs AND (1-3 OR 7)
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
COL = 0.233  # and tiles in a row this far
TITLE_GAP = 0.137  # a region's title sits this far above the caught height of the first row under it
FIT = 0.015  # a number this close to a row height sits at it
SCROLL = 0.25  # of the screen per swipe, ~1.7 rows: the clear band shows ~4.5, so each screen repeats ~2 rows
MAX_SCREENS = 400
SURE_ROOM = 0.15  # a number this far inside the clear band, top or bottom, sits among enough rows to read it right
LAST_DEX = 1025  # Pecharunt, the highest number in the game master: any higher read is an OCR slip
REGION_NAMES = {"KANTO", "JOHTO", "HOENN", "SINNOH", "UNOVA", "KALOS", "ALOLA", "GALAR", "HISUI", "PALDEA"}
# not on the Lucky or the 100% page at all: the species that can't be traded (Mew, Celebi, Jirachi, Deoxys,
# Phione to Arceus, the Unova and Kalos mythicals, Zygarde, Magearna, Marshadow, Zeraora, Meltan, Melmetal, Zarude)
NEVER_TRADED = {999, 1000}  # Gimmighoul, Gholdengo: shown on the Lucky page, but can't be traded, so never lucky
NOT_LISTED = {151, 251, 385, 386, *range(489, 495), 647, 648, 649, *range(718, 722), 801, 802, 807, 808, 809, 893}


# ---------- reading ----------

def numbers(texts):
    """the 4-digit Pokédex numbers on screen -> [(n, text box)]"""
    out = []
    for t in texts:
        s = t[4].replace("O", "0").replace("o", "0").strip()
        if re.fullmatch(r"\d{4}", s) and 0 < int(s) <= LAST_DEX:  # a tile near #210 once read as 6810 (2026-11-11)
            out.append((int(s), t))
    return out


FAR = 40  # further than this from a screen's middle number is a misread


def near(texts):
    """numbers(texts) without misreads: one screen holds about 30 numbers in a row (0560 read as 0990 among 547-569,
    Lucky page 2026-11-22)"""
    got = numbers(texts)
    mid = statistics.median([n for n, _ in got] or [0])
    return [(n, t) for n, t in got if abs(n - mid) <= FAR]

FLIPPED = re.compile(r"[0-9OoIlTZEL£+S]{4}")  # a grid number read upside down: 'T000' 0001, 'ZIOO' 0012


def flipped(texts):
    """the OCR read a grid number upside down: a 4-letter label that isn't a number (the Lucky page, Pixel,
    2026-11-22: rows 1-12 as 'T000 2000 £000 +000'..., and once only 0481 as '18+0')"""
    return any(FLIPPED.fullmatch(t[4].strip()) and not numbers([t]) for t in texts)


def more_numbers(texts, more):
    """texts, plus the numbers in more that texts don't have. Where both read a number on one spot, the one that fits
    its row better stays: a turned read of a label already read upright gives a wrong number on it (a jump to #979
    stopped the Lucky page at #367), and the plain read took 0820 for 0780 between 0819 and 0821 (2026-11-22)"""
    top, bottom = band(texts)
    # (a number read under the chips doesn't count: 0698 half under them read as 0693, and kept the sharp read's
    # real #693 out, Lucky page 2026-11-22. read_grid skips those spots anyway)
    have = [(n, t) for n, t in near(texts) if not hidden(t, top, bottom)]
    extra = [(n, t) for n, t in near(more) if not hidden(t, top, bottom)]
    mid = lambda t: (t[0] + t[2] / 2, t[1] + t[3] / 2)
    same = lambda a, b: abs(mid(a)[0] - mid(b)[0]) < 0.06 and abs(mid(a)[1] - mid(b)[1]) < 0.02

    def fit(n, t):
        """how many numbers in its row, from either read, agree with n: one more for each tile to the right"""
        return sum(abs(mid(u)[1] - mid(t)[1]) < 0.02 and not same(u, t) and m - n == round((mid(u)[0] - mid(t)[0]) / COL)
                   for m, u in have + extra)
    known = {m for m, _ in have}
    drop, add = [], []
    for n, t in extra:
        if n in known:
            continue
        here = [(m, u) for m, u in have if same(u, t)]
        if not here:
            add.append(t)
        elif here[0][0] != n and fit(n, t) > fit(*here[0]):
            drop.append(here[0][1])
            add.append(t)
    return [t for t in texts if not any(t is d for d in drop)] + add


def upright(path, texts):
    """texts, plus the numbers a turned copy reads that these miss, when rows read upside down. Neither read gets
    them all: the ★100% grid read 17 numbers plain and 10 turned (2026-11-11), the Lucky one 4 plain, 16 turned"""
    return more_numbers(texts, ui.ocr_turned(path)) if flipped(texts) else texts


def band(texts):
    """the part of the grid nothing covers -> (top, bottom). The region header grows at the top and bottom of the
    grid, and the chips sit over the bottom rows."""
    top = HEADER_BIG if "RECENTLY" in ui.joined(texts) else HEADER_SMALL
    chips = [t[1] for t in texts if t[1] > 0.78 and re.search(r"SHINY|LUCKY|XXL|XXS|SHADOW|PURIFIED|100%|POK",
                                                              t[4].upper())]
    return top, (min(chips) if chips else CHIP_Y) - 0.025


def hidden(t, top, bottom):
    """a number's box under the header or the chips (top, bottom from band): the next screen has it whole"""
    return t[1] - ABOVE[1] - MIN_BOX < top or t[1] + t[3] > bottom


def spread(im, t, top):
    """how busy the tile is just above its number: a picture, or plain tile. The box stops at the header (top)."""
    W, H = im.size
    cx, y = t[0] + t[2] / 2, t[1]
    box = im.crop((int((cx - HALF_W) * W), int(max(y - ABOVE[0], top) * H), int((cx + HALF_W) * W),
                   int((y - ABOVE[1]) * H)))
    return statistics.pstdev(box.convert("L").getdata())


def read_grid(path, texts, known=None):
    """-> ({n: True if missing}, [(n, y, spread, missing)] for the log). Raises Stop when it can't tell, unless
    known ({n: missing}, from earlier screens) has it: the page's end scrolls #1023 and #1024, read before, up under
    the header, with nothing to measure them by (Lucky page, 2026-11-22).

    The number's height decides. Rows are PITCH apart, a caught number at the bottom of its tile and a missing one
    DROP higher. The sure tiles on the screen pin those heights down: a busy picture (caught), a plain tile (missing),
    any row with numbers at two heights (the lower ones caught), and a region's title. The spread backs it up."""
    im = Image.open(path).convert("RGB")
    top, bottom = band(texts)
    # a title half under the header counts: ALOLA at 0.126-0.146 with the header ending at 0.13. Only a region's
    # name: the header's own count can read as CLIO there (2026-11-11)
    title_boxes = [t for t in texts if top < t[1] + t[3] and t[1] < bottom and t[4].strip() in REGION_NAMES]
    tiles = []
    for n, t in near(texts):
        if hidden(t, top, bottom):
            continue  # under the header or the chips: the next screen has it whole
        # the box stops at a region's title too: ALOLA's letters sit in the box over a missing #722 (2026-11-11)
        cut = max([top] + [b[1] + b[3] for b in title_boxes if b[1] < t[1]])
        tiles.append((n, t[1], spread(im, t, cut)))
    tiles.sort(key=lambda r: r[1])
    # a region's title (SINNOH) between two regions starts a new grid: heights only carry within one part
    titles = sorted(b[1] for b in title_boxes)
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
            elif known and n in known:
                missing = known[n]
            else:
                raise Stop(f"can't tell #{n} (height {y:.3f}, spread {s:.1f}): {tiles}")
        if (missing and s >= BUSY_MIN) or (not missing and s <= SURE_PLAIN):
            raise Stop(f"#{n} sits like a {'missing' if missing else 'caught'} one but its spread is {s:.1f}: {tiles}")
        rows.append((n, y, s, missing))
    return {r[0]: r[3] for r in rows}, rows


# ---------- getting there ----------

def regions_button(texts):
    """the grid's REGIONS button label, also when OCR drops a letter ("REIONS", 2026-11-11)"""
    return any(difflib.SequenceMatcher(None, t[4].upper().strip(), "REGIONS").ratio() >= 0.8 for t in texts)


def caught_total(path, texts):
    """the region list's 'Caught: 935' at the top right -> 935, or None. The red 'GPS signal not found' banner
    (location off for the run) covers it: its own text runs into the line there ('(11) ght: 935'), so under it only
    the number after the colon counts, read from a contrast-boosted crop (Pixel, 2026-11-22)"""
    if ui.gps_banner():
        texts = ui.under_gps_banner(path, 0.5, 0.06, 1.0, 0.12)
        pat = r"GHT\s*[:;]\s*(\d[\d,]*)\s*$"
    else:
        pat = r"CAUGHT\D*(\d[\d,]*)"
    m = next((m for t in texts if t[1] < 0.1 for m in [re.search(pat, t[4].upper())] if m), None)
    return int(m.group(1).replace(",", "")) if m else None


def where(path, texts):
    j = ui.joined(texts)
    if numbers(texts) and ("REGIONS" in j or regions_button(texts)):
        return "grid"
    if flipped(texts) and regions_button(ui.ocr_turned(path)):  # read upside down, REGIONS too: 'SNOI...' (Pixel's
        return "grid"  # 2x retry on the Lucky page, 2026-11-22: 20 looks in a row 'unknown')
    if "FILTER BY" in j:
        return "dex-search"
    if "POK" in j and "KANTO" in j and caught_total(path, texts) is not None:
        return "regions"
    return home.where(path, texts)


def look():
    return base.look(where)


def tap_at(fx, fy, bounds, wait=1.6):
    base.click(fx, fy, bounds, fuzz=0.006, rest=wait)


def tap_text(texts, bounds, pred, dy=0.0):
    t = next((t for t in texts if pred(t)), None)
    if not t:
        return False
    base.tap_box(t, bounds, dy=dy, fuzz=0.006, rest=1.6)
    return True


def swipe(fx1, fy1, fx2, fy2, bounds):
    """the grid, the chip row and the region list: lists, so on Android they settle as fast as the Pokémon list"""
    base.drag(fx1, fy1, fx2, fy2, bounds, ms=random.randint(450, 600), settle=0.8,
              android_settle=base.LIST_SETTLE, bring_front=False)


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
            n = caught_total(path, texts)
            if n is None:
                raise Stop("can't read the page's Caught total")
            return n, texts, bounds
        if t:
            log(f"tapping the {label} chip")
            tap_at(*ui.center(t), bounds)
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
    seen, last_max, still, backs = {}, None, 0, 0
    room = {}  # n -> how far from the band's edge it was when read: a read nearer the middle is surer
    edge = [0.0, 999.0]  # busiest missing tile, plainest caught one: how close the spread alone came to a wrong call
    for i in range(MAX_SCREENS):
        screen, texts, path, bounds = base.settle(look, lambda r: r[0] == "grid", 3)  # one odd read: look again
        if screen != "grid":
            keep_capture("grid")
            raise Stop(f"not on the Pokédex grid any more ({screen})")
        texts = upright(path, texts)
        got, rows = read_grid(path, texts, seen)
        def holes():
            """skipped numbers in the rows between the top and bottom ones read: those can be half in (a missing
            number sits higher than a caught one)"""
            lines = []  # rows read, top to bottom
            for n, y, *_ in sorted(rows, key=lambda r: r[1]):
                if lines and y - lines[-1][0] < DROP + 0.02:
                    lines[-1][1].append(n)
                else:
                    lines.append((y, [n]))
            if len(lines) < 3:
                return []
            return [n for n in range(min(lines[1][1]), max(lines[-2][1]))
                    if n not in got and n not in NOT_LISTED]
        if holes():  # the OCR skipped a number: read the phone's own screenshot at 3x
            log(f"  didn't read {holes()}: reading a sharper screenshot")
            # the same screenshot, sharper: a new one can catch the list a bit further on, and its numbers then sit
            # at other heights than the first read's (#463 at 0.789 among rows at 0.808, Lucky page 2026-11-22)
            sharp = ui.android.sharp_last()
            # (it adds to what's read: alone, it lost 480 and 482 that the first read had, Lucky page 2026-11-22)
            texts = more_numbers(texts, upright(sharp, ui.ocr(sharp)))
            got, rows = read_grid(path, texts, seen)
            if holes():
                keep_capture("holes")
                raise Stop(f"can't read {holes()} on this screen")
        if not got:
            keep_capture("grid")
            raise Stop("read no numbers on this screen")
        if i == 0 and 1 not in got:
            keep_capture("grid")
            raise Stop(f"the grid didn't open at #1 (first number read: {min(got)})")
        hi, lo = band(texts)
        here = {n: min(y - hi, lo - y) for n, y, *_ in rows}
        clash = [n for n in got if n in seen and seen[n] != got[n]]
        for n in clash:  # the read nearer the middle wins: #960 (a pale Wiglett) read missing at the bottom edge,
            # caught a row up the next screen (Lucky page, 2026-11-22). Both well inside the band: can't tell
            if min(here[n], room[n]) < SURE_ROOM and here[n] != room[n]:
                if here[n] < room[n]:
                    got[n] = seen[n]
                log(f"  #{n} read both ways: {'missing' if got[n] else 'caught'}, from the read further from the edge")
        clash = [n for n in got if n in seen and seen[n] != got[n]]
        if clash:
            keep_capture("clash")
            raise Stop(f"read these both ways on two screens: {clash}")
        # no number shared is fine when only numbers the page never shows sit between: 646 then 650 (2026-11-11)
        if seen and not set(got) & set(seen) and set(range(max(seen) + 1, min(got))) - NOT_LISTED:
            # the list was still moving when the last screen was read, so this swipe went further: go back a bit
            # (531 read, then 535-550, Lucky page, Pixel under load, 2026-11-22)
            if backs < 2:
                backs += 1
                log(f"  skipped past {max(seen) + 1}-{min(got) - 1}: scrolling back")
                x, y = random.uniform(0.3, 0.7), random.uniform(0.3, 0.36)
                swipe(x, y, x + random.uniform(-0.02, 0.02), y + SCROLL, bounds)
                continue
            keep_capture("gap")
            raise Stop(f"this screen shares no number with the last one: rows may be skipped ({min(got)}-{max(got)})")
        backs = 0
        new = sorted(n for n in got if n not in seen)
        for n, y, s, m in rows:
            edge[0 if m else 1] = max(edge[0], s) if m else min(edge[1], s)
        seen.update(got)
        room.update({n: max(here[n], room.get(n, -1)) for n in got})
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

ranges = search.dex_ranges  # {1, 2, 3, 7} -> ['1-3', '7'] (tradeable.py uses it too)


def searches(ns, prefix=""):
    """comma lists of at most MAX_CHARS characters, each with prefix in front"""
    out, cur = [], ""
    for r in ranges(ns):
        if cur and len(prefix) + len(cur) + 1 + len(r) > MAX_CHARS:
            out.append(prefix + cur)
            cur = ""
        cur = f"{cur},{r}" if cur else r
    return out + [prefix + cur] if cur else out


parse = search.dex_numbers  # '14,22,29-33' -> {14, 22, 29, ..., 33}


# ---------- Lucky and XXS: what a lucky or XXS Pokémon in storage could evolve into ----------
# Both keep their mark when they evolve, so the step is the same for both pages: only the search word differs.

EVOLVE = {"lucky": ("lucky", "Lucky"), "xxs": ("xxs", "XXS")}  # page -> (its storage search word, its name in reports)

REGIONS = {"_alolan": "alola", "_galarian": "galar", "_hisuian": "hisui", "_paldean": "paldea"}
GENDER = {413: "female", 414: "male", 416: "female", 475: "male", 478: "female", 758: "female"}  # only this gender evolves into it
NO_EVOLVE = {589, 617}  # Escavalier, Accelgor: need a trade. A lucky one can't be traded again; an XXS one would leave
UNSURE = {"wurmple": "Wurmple turns into Silcoon or Cascoon at random",
          "basculin": "only White-Striped Basculin evolves, and a search can't pick it out"}


def evo_tree():
    """(by, parent): speciesId -> its game data entry (no shadow, mega or XL), and child -> what it evolves from in
    GO (pvp.parent: the one evolution map)"""
    by = {s: p for s, p in pvp.SPECIES.items() if not re.search(r"_shadow|_mega|_xl$", s)}
    return by, {c: p for c in by if (p := pvp.parent(c))}


def form_terms(sid, by):
    """the search terms that pick out this form of its species"""
    suffix = next((x for x in REGIONS if x in sid), None)
    if suffix:
        return f"&{REGIONS[suffix]}"
    dex = by[sid]["dex"]  # the plain form: leave out its regional forms
    return "".join(f"&!{r}" for x, r in REGIONS.items() if any(p["dex"] == dex and x in o for o, p in by.items()))


def source_query(sids, by, gender=None, word="lucky"):
    """the storage search for lucky (or xxs: word) copies of these species forms (same form terms) that can still
    evolve"""
    dexes = ",".join(str(by[x]["dex"]) for x in sids)
    return f"{word}&{dexes}&!costume{form_terms(sids[0], by)}" + (f"&{gender}" if gender else "")


def ancestors(sid, parent):
    out = []
    while sid in parent:
        sid = parent[sid]
        out.append(sid)
    return out


# ---------- ★100%: which new copies fill a hole ----------

def hundred_useful(missing, owned, by=None, parent=None):
    """-> the species forms a new 100% copy of would fill a ★100% hole with, itself or by evolving.
    The page never got the 100s caught before it came out, so a later stage on the page counts for the earlier
    ones: Pidgeot there, Pidgey's hole is filled. owned {sid: n}: the 100 copies storage holds now (count_owned).
    The page only says one was there once: a Magnemite on it that's gone since evolves into nothing. Each copy goes
    down one branch and fills every number on the way: a 100 Eevee fills one missing Eeveelution, and each other
    missing one wants a new Eevee. A hole is a number, so its forms fill it alike: two plain 100 Diglett fill
    Dugtrio's, and no Alolan Diglett is wanted. Only Hisuian Sneasel reaches Sneasler, so a plain one can't fill it.
    The forms joined by evolving or by a shared number are judged together (ways_left)"""
    if by is None:
        by, parent = evo_tree()
    kids = {}
    for c, p in parent.items():
        kids.setdefault(p, []).append(c)

    def below(s):
        out, todo = [], list(kids.get(s, []))
        while todo:
            out.append(todo.pop())
            todo += kids.get(out[-1], [])
        return out

    def paths(s):
        """the numbers on each way down from s to a last stage"""
        return [{by[s]["dex"]} | p for k in kids[s] for p in paths(k)] if s in kids else [{by[s]["dex"]}]

    top = {s: s for s in by}

    def root(s):
        while top[s] != s:
            s = top[s]
        return s
    first = {}
    for s in by:
        if s in parent:
            top[root(s)] = root(parent[s])
        d = by[s]["dex"]
        if d in first:
            if root(s) != root(first[d]):
                top[root(s)] = root(first[d])
        else:
            first[d] = s
    groups = {}
    for s in by:
        groups.setdefault(root(s), []).append(s)

    out = set()
    for forms in groups.values():
        later = {by[s]["dex"] for s in forms if any(by[k]["dex"] not in missing for k in below(s))}
        holes = {by[s]["dex"] for s in forms if by[s]["dex"] in missing} - later
        if not holes:
            continue
        ways = {s: sorted({frozenset(p & holes) for p in paths(s)} - {frozenset()}, key=sorted) for s in forms}
        now = ways_left(holes, ways, owned)
        if now:
            out |= {s for s in forms if ways[s] and ways_left(holes, ways, owned, s) < now}
    return out


def ways_left(holes, ways, owned, extra=None):
    """the fewest holes left after every copy (owned, plus one of extra) is sent down one of its ways: every way to
    send them is tried. Copies of one form are alike, so only which ways they take counts, not which copy takes
    which"""
    import itertools
    pools = []
    for s, w in ways.items():
        n = min(owned.get(s, 0) + (s == extra), len(holes))
        if n and w:
            pools.append(list(itertools.combinations_with_replacement(w, n)))
    best = len(holes)
    for pick in itertools.product(*pools):
        best = min(best, len(holes - set().union(*(x for ch in pick for x in ch))))
        if not best:
            break
    return best


def hundo_sources(missing, by, parent):
    """the species forms on the ★100% page with a missing number below them: the only ones whose 100 copies in
    storage change hundred_useful's answer (an old 100 at a missing number isn't counted: a new copy is still asked
    for, as before)"""
    out = set()
    for sid in parent:
        if by[sid]["dex"] in missing:
            out |= {a for a in ancestors(sid, parent) if by[a]["dex"] not in missing}
    return sorted(out, key=lambda s: (by[s]["dex"], s))


def count_owned(missing, by, parent):
    """{sid: n} of hundo_sources' 100 copies in storage now, with counts only (no Pokémon opened): dex numbers in
    groups of 20, halved where a group finds some (tagsheet.group_hits), then one count per form of each number
    found. Saved as owned-100.json in the run folder"""
    srcs = hundo_sources(missing, by, parent)
    dexes = sorted({by[s]["dex"] for s in srcs})
    log(f"★100%: counting the 100s in storage of {len(srcs)} forms on the page with a missing number below")
    to_storage()
    count = counter({}, edit=True, live=True)  # (as evolvable: edit the last search's end, count with the keyboard up)
    seen, hits = [0, 0], []
    for i in range(0, len(dexes), 20):
        hits += tagsheet.group_hits([(d, [d]) for d in dexes[i:i + 20]], "4*&", "!costume", count, seen)
    owned = {}
    for d in hits:
        for s in (s for s in srcs if by[s]["dex"] == d):
            if n := count(source_query([s], by, word="4*")):  # (a plain form with no regional one: cached already)
                owned[s] = n
    log(f"  100s in storage: {owned}")
    import json
    base.write_json(os.path.join(base.RUN_DIR, "owned-100.json"), owned, indent=0)
    return owned


def owned_100(run):
    """a ★100% run's count_owned answer, or None (a run from before it counted)"""
    import json
    f = os.path.join(run, "owned-100.json")
    return json.load(open(f)) if os.path.exists(f) else None


def lines(missing):
    """the families where a lucky Pokémon could evolve to fill a hole -> [(sources, targets)]: the species forms in
    the page that a lucky copy could start from, and the missing forms one of them could reach"""
    by, parent = evo_tree()
    groups = {}
    for sid, p in by.items():
        if p["dex"] not in missing or sid not in parent or p["dex"] in NO_EVOLVE:
            continue
        chain = ancestors(sid, parent)
        if all(by[a]["dex"] in missing for a in chain):
            continue  # nothing above it on the page: no lucky copy to start from
        srcs, ts = groups.setdefault(chain[-1], (set(), set()))
        srcs |= {a for a in chain if by[a]["dex"] not in missing}
        ts |= {a for a in [sid] + chain if by[a]["dex"] in missing}
    return by, parent, list(groups.values())


def route(src, dst, parent, by):
    """evolving src all the way to dst -> (dex numbers it fills, the gender src has to be or None).
    None if dst isn't below src."""
    if src not in ancestors(dst, parent):
        return None
    fills, gender, s = set(), None, dst
    while s != src:
        fills.add(by[s]["dex"])
        gender = gender or GENDER.get(by[s]["dex"])
        s = parent[s]
    return fills, gender


def covered(targets, counts, parent, by):
    """can these lucky copies fill every missing number in the line? counts: {(source, gender or None): n}.
    Each copy evolves down one branch: try every way to send them."""
    import itertools
    want = {by[t]["dex"] for t in targets}
    copies = []
    for (src, gender), n in counts.items():
        ways = [r[0] for t in targets if (r := route(src, t, parent, by)) and r[1] in (None, gender)]
        copies += [ways] * min(n, len(want))
    return any(want <= set().union(*pick) for pick in itertools.product(*[[set()] + w for w in copies]))


search_exact = tagsheet.count_exact  # q -> its result count, typed exactly (shared)
counter = tagsheet.counter  # -> n(q): counts kept in a cache, lost searches tried again (shared)


def to_storage():
    """from the Pokédex to the Pokémon list"""
    for _ in range(6):
        screen, texts, path, bounds = look()
        if screen not in ("grid", "dex-search", "regions"):
            break
        ui.android.key("back")
        time.sleep(1.5)
    home.start()


def evolvable(missing, page="lucky"):
    """the missing numbers a lucky (or XXS: page) Pokémon in storage could evolve to fill, a whole line at a time.
    -> (numbers to drop from the search, report lines, dex numbers of the ones to keep)"""
    word, Name = EVOLVE[page]
    by, parent, groups = lines(missing)
    name = lambda sid: re.sub(r" \((Male|Female)\)$", "", by[sid]["speciesName"])
    log(f"{Name}: {len(groups)} lines a {word} Pokémon could evolve into a missing number")
    to_storage()
    # counts only, small ones: edit the end of the last search and read the count with the keyboard up (as roster)
    count = counter({}, edit=True, live=True)
    drop, report, keep = set(), [], set()
    for srcs, targets in sorted(groups, key=lambda g: min(by[t]["dex"] for t in g[1])):
        srcs = sorted(srcs, key=lambda x: by[x]["dex"])
        routes = {(x, t): route(x, t, parent, by) for x in srcs for t in targets}
        genders = {r[1] for r in routes.values() if r}
        sexed = genders != {None}
        genders = ("male", "female") if None in genders else sorted(genders)  # genderless never needs a gender
        one_way = (not sexed and not set(srcs) & set(UNSURE) and all(routes.values())
                   and len({form_terms(x, by) for x in srcs}) == 1
                   and any(targets <= {e, *ancestors(e, parent)} for e in targets))
        counts = {}
        if one_way:  # every copy of every source runs through all the holes: one search for all of them
            n = count(source_query(srcs, by, word=word))
            if n:
                counts[(srcs[0], None)] = n  # (any copy fills them all)
        else:
            for x in srcs:
                for gender in (genders if sexed else (None,)):
                    n = count(source_query([x], by, gender, word))
                    if n:
                        counts[(x, gender)] = n
        log(f"  {','.join(ranges({by[t]['dex'] for t in targets}))}: {word} {counts}")
        have = ", ".join(f"{n} {'/'.join(name(x) for x in srcs) if one_way else name(x)}" + (f" {g}" if g else "")
                         for (x, g), n in counts.items())
        what = f"{','.join(ranges({by[t]['dex'] for t in targets}))} " \
               f"({', '.join(sorted({name(t) for t in targets}))})"
        unsure = [x for x, g in counts if x in UNSURE]
        sure = {k: n for k, n in counts.items() if k[0] not in UNSURE}
        # every one that could help, even a maybe (Wurmple) or too few (2 Applin for 3 branches): keep them
        # all until the hole is filled
        keep |= {by[x]["dex"] for x in srcs if one_way and counts or any(k[0] == x for k in counts)}
        if sure and covered(targets, sure, parent, by):
            drop |= {by[t]["dex"] for t in targets}
            report.append(f"evolve: {what} from {word} {have}")
        elif unsure:
            report.append(f"kept, check by hand: {what}. You have {word} {have}, but {UNSURE[unsure[0]]}")
        elif counts:
            report.append(f"kept: {what}. {Name} {have} can't fill all of them")
    return drop, report, keep


def run_page(page):
    label = PAGES[page]
    texts, bounds = to_regions()
    total, texts, bounds = pick_page(label)
    log(f"{label} page: {total} caught")
    if not tap_text(texts, bounds, lambda t: ui.up(t) == "KANTO"):
        swipe(0.5, 0.3, 0.5, 0.75, bounds)  # region list scrolled down: back to the top
        screen, texts, path, bounds = look()
        if not tap_text(texts, bounds, lambda t: ui.up(t) == "KANTO"):
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
    with open(os.path.join(base.RUN_DIR, f"page-{page}.txt"), "w") as f:
        f.write(",".join(ranges(missing)) + "\n")
    write_searches(page, missing)


def write_searches(page, missing):
    """the searches to paste, saved in the run folder. Lucky and XXS: first take out what a lucky or XXS Pokémon here
    could evolve into"""
    label, report = PAGES[page], []
    if page in EVOLVE:
        word = EVOLVE[page][0]
        never = set(missing) & NEVER_TRADED
        # Gimmighoul is never lucky, so the Lucky step skips it; an XXS Gimmighoul here can fill Gholdengo
        drop, report, keep = evolvable(set(missing) - never if page == "lucky" else set(missing), page)
        never -= drop
        missing = sorted(set(missing) - drop - never)
        if never:
            report.append(f"left out, can't be traded: {','.join(ranges(never))}")
        if keep:  # (it also finds the wrong form or gender of a few of them: those are fine to tag too)
            report.append(f"tag these before you clean up, so they get evolved: {word}&!costume&{','.join(ranges(keep))}")
        with open(os.path.join(base.RUN_DIR, f"evolve-{page}.txt"), "w") as f:
            f.write("\n".join(report) + "\n")
    if page == "100":
        by, parent = evo_tree()
        want = {by[s]["dex"] for s in hundred_useful(set(missing), count_owned(set(missing), by, parent), by, parent)}
        known = {p["dex"] for p in by.values()}
        filled = sorted(n for n in missing if n in known and n not in want)
        extra = sorted(want - set(missing))
        missing = sorted(want | {n for n in missing if n not in known})
        if filled:
            report.append(f"left out, a later stage is on the page: {','.join(ranges(filled))}")
        if extra:
            report.append(f"added, on the page but a missing branch wants another copy: {','.join(ranges(extra))}")
    out = searches(missing, PREFIX.get(page, ""))
    with open(os.path.join(base.RUN_DIR, f"missing-{page}.txt"), "w") as f:
        f.write("\n\n".join(out) + "\n")
    if report:
        print(f"\n{EVOLVE[page][1]} Pokémon you have that could evolve into a missing one:" if page in EVOLVE else
              "\nThe page, with later stages counted for earlier ones:")
        print("\n".join(f"  {r}" for r in report))
    print(f"\nWanted for the {label} page: {len(missing)} Pokémon, {len(out)} search(es)\n")
    for i, s in enumerate(out, 1):
        print(f"--- search {i} of {len(out)} ({len(s)} characters) ---\n{s}\n")
    print(f"saved to {os.path.join(base.RUN_DIR, f'missing-{page}.txt')}")


def save_trainer(name):
    """which account this run read: other skills pick a run by it (latest())"""
    with open(os.path.join(base.RUN_DIR, "trainer.txt"), "w") as f:
        f.write(name + "\n")


trainer_of = base.trainer_of  # a run folder -> its account


def latest(page, trainer):
    """-> (the newest run's missing numbers, its folder) for this page and account, or (None, None). Lucky: an
    evolve-lucky run counts (its search already leaves out what a lucky Pokémon can evolve into)"""
    runs = os.path.join(HERE, "runs")
    ok = [d for d in sorted(os.listdir(runs), reverse=True) if os.path.isdir(os.path.join(runs, d))
          and d.endswith("-" + page) and trainer_of(os.path.join(runs, d)) == trainer
          and os.path.exists(os.path.join(runs, d, f"missing-{page}.txt"))]
    if not ok:
        return None, None
    run = os.path.join(runs, ok[0])
    f = "page-100.txt" if page == "100" and os.path.exists(os.path.join(run, "page-100.txt")) else f"missing-{page}.txt"
    return read_numbers(os.path.join(run, f), page), run  # ★100%: the page as read (callers use hundred_useful)


def read_numbers(path, page):
    """a saved page or search file -> its dex numbers (an XXS search starts with xxs&: taken off first)"""
    return parse(open(path).read().replace(PREFIX.get(page, ""), ""))


def cmd_look():
    screen, texts, path, bounds = look()
    print(f"screen: {screen}, band {band(texts)}")
    if screen == "grid":
        got, rows = read_grid(path, texts)
        for n, y, s, m in rows:
            print(f"  #{n:4}  y {y:.3f}  spread {s:5.1f}  {'MISSING' if m else 'caught'}")


def cmd_evolve(page, run):
    """the Lucky (or XXS) step again on a page already read: storage changed, or the rules did. ★100%: the count of
    100s in storage again (count_owned), on the account that read the page"""
    runs = os.path.join(HERE, "runs")
    files = (f"page-{page}.txt",) if page == "100" else (f"page-{page}.txt", f"missing-{page}.txt")
    # (★100%'s missing-100.txt is the wanted list, not the page)
    if not run:
        run = max((d for d in os.listdir(runs) if d.endswith(f"-{page}") and not d.endswith(f"-evolve-{page}")
                   and any(os.path.exists(os.path.join(runs, d, f)) for f in files)), default=None)
        if not run:
            sys.exit(f"no {PAGES[page]} run yet: dex.py {page}")
    run = os.path.join(runs, run) if not os.path.isabs(run) else run
    path = next(os.path.join(run, f) for f in files if os.path.exists(os.path.join(run, f)))
    missing = sorted(read_numbers(path, page))
    base.new_run_dir(runs, suffix=f"evolve-{page}")
    who = trainer_of(run)
    if page == "100":
        now = home.trainer()
        if who and now != who:
            raise Stop(f"the page is {who}'s, but {now} is signed in: its 100s can't be counted")
        who = who or now
        with open(os.path.join(base.RUN_DIR, "page-100.txt"), "w") as f:  # (latest() reads this run's page)
            f.write(",".join(ranges(missing)) + "\n")
    if who:
        save_trainer(who)
    log(f"page from {path}: {len(missing)} missing" + (f" ({who})" if who else ""))
    write_searches(page, missing)


def script(page):
    save_trainer(home.trainer())
    run_page(page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page", choices=(*PAGES, "look", "evolve"))
    ap.add_argument("rest", nargs="*", metavar="[lucky|xxs|100] [run]",
                    help="evolve: which page (default lucky), and a run's folder (default: the newest)")
    a = ap.parse_args()
    if not ui.ANDROID:
        sys.exit("Android only for now: POGO_PHONE=android")
    if a.page == "look":
        return cmd_look()
    if a.page == "evolve":
        page = a.rest.pop(0) if a.rest and a.rest[0] in (*EVOLVE, "100") else "lucky"
        if len(a.rest) > 1:
            ap.error("evolve takes a page and one run folder at most")
        return session.main(cmd_evolve, page, a.rest[0] if a.rest else None)
    base.new_run_dir(os.path.join(HERE, "runs"), suffix=a.page)
    session.main(script, a.page)


if __name__ == "__main__":
    main()
