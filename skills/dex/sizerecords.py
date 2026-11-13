#!/usr/bin/env python3
"""/sizerecords: read each species' MY RECORDS box off the Pokédex (lightest, heaviest, shortest, tallest), then say
which account's record would beat the other's, so a spare xxs or XXL can be traded over to set a new record.
Android only for now.

  POGO_PHONE=android caffeinate -dimsu python3 sizerecords.py read [--from N] [--limit N] [--again]
                                                   read this account's Pokédex
  python3 sizerecords.py compare                   the trades (no phone)

read: gets to the Pokédex from anywhere (main menu, POKÉDEX, the POKÉMON chip, the start's region), opens the nearest
tile, walks to the start page by its title and taps INFO. Each page's title says its number and name. One drag up
brings the MY RECORDS box on screen. A sideways swipe goes to the next species and keeps the INFO tab (a page that
opens on CAUGHT gets INFO tapped again). About 4 s a species, so the whole Pokédex is over an hour. Each species is
saved to the database (pokedb.save_record) as soon as it's read, so a stopped run loses nothing. The start: --from N,
or else the first species not read in the last FRESH_HOURS, so a rerun picks up where a stop left off. Species read
in that time are swiped past (--again reads them anyway). --limit N reads at most N species. It only taps to move
around: it never changes anything in the game.

A page with no MY RECORDS box, or no tabs at all (never caught; a form like Alolan Rattata, 2026-11-12) is saved with
no values. The box looks like it counts only Pokémon caught as that species: CyrillJan's Milotic (CAUGHT 1, evolved),
Huntail, Gorebyss, Ludicolo and Beautifly have none (2026-11-12). So whether a traded one sets a record is not known
yet: read the receiver's page before and after a trade. Forms:
the swipe shows one page per number, and this reads the form the page opens on (the first one). Another form's own
box isn't read.

compare: for every species both accounts have records for, each record one account beats (strictly: the box shows two
decimals, so a tie may not be a new record). Each line gives a storage search for the giver to find candidates: xxs,xs
for the lightest and shortest, xxl,xl for the heaviest and tallest. The record holder itself may be gone (transferred,
evolved), so open the hits and check their weight or height. Saved in runs/<time>-compare/trades.txt too.
"""
import argparse, os, re, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
sys.path.insert(0, HERE)
import ui
import base
from base import Stop, log
import session, home, pokedb
import dex

FRESH_HOURS = 12
TITLE = re.compile(r"(?:^|\s)(\d{4})\s+([^\W\d_].*)$")  # '© 0029 NIDORAN f': the grid's numbers have no name
VALUE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(kg|m)l?$")  # '0.14 ml': OCR adds an l
BOX_ROWS = 0.14  # the values sit within this far below the MY RECORDS label
SWIPE_NEXT = (0.85, 0.5, 0.15, 0.5)
ACCOUNTS = ("HashTagAJay", "CyrillJan")
REGIONS = (("KANTO", 1), ("JOHTO", 152), ("HOENN", 252), ("SINNOH", 387), ("UNOVA", 494), ("KALOS", 650),
           ("ALOLA", 722), ("GALAR", 810), ("HISUI", 899), ("PALDEA", 906))  # the region list, and each one's first number
# the records, the side of the box they're on, which way beats, and the storage search for candidates
KINDS = (("kg_min", "lightest", "kg", -1, "xxs,xs"), ("kg_max", "heaviest", "kg", 1, "xxl,xl"),
         ("m_min", "shortest", "m", -1, "xxs,xs"), ("m_max", "tallest", "m", 1, "xxl,xl"))


# ---------- reading one page ----------

def title(texts):
    """the page's '0019 RATTATA' -> (19, 'RATTATA'), or None (scrolled off, or not a species page)"""
    for t in texts:
        if t[1] > 0.5:
            continue
        m = TITLE.search(t[4].strip())
        if m and 0 < int(m.group(1)) <= dex.LAST_DEX:
            name = re.split(r"[^\w .'’:♀♂-]|\s\d", m.group(2))[0].strip()  # 'PIKACHU? 0 100%': the status bar
            return int(m.group(1)), name
    return None


def tabs(texts):
    """the CAUGHT / INFO / BATTLE row: INFO's box, or None"""
    words = {ui.up(t) for t in texts}
    if not {"INFO", "BATTLE"} <= words:
        return None
    return next(t for t in texts if ui.up(t) == "INFO")


def has_label(texts):
    """the MY RECORDS label's text box, or None"""
    return next((t for t in texts if ui.up(t).replace(" ", "") == "MYRECORDS"), None)


def box(texts):
    """the MY RECORDS box -> 'none' (the page ends with no box), 'low' (the label's on screen, its values aren't),
    None (nothing to tell yet), or (kg_min, kg_max, m_min, m_max)"""
    label = has_label(texts)
    if not label:
        if caught_tab(texts):  # not on INFO
            return None
        return "none" if any(ui.up(t) == "EVOLUTION" or ui.up(t).startswith("SEE ALL ") for t in texts) else None
    vals = {"kg": [], "m": []}
    for t in texts:
        m = VALUE.match(t[4].strip())
        if m and label[1] < t[1] < label[1] + BOX_ROWS:
            vals[m.group(2)].append((t[0], float(m.group(1).replace(",", "."))))
    if len(vals["kg"]) != 2 or len(vals["m"]) != 2:
        return "low" if label[1] > 1 - BOX_ROWS - 0.05 else None
    (kg_min, kg_max), (m_min, m_max) = ([v for _, v in sorted(vals[u])] for u in ("kg", "m"))
    if kg_min > kg_max or m_min > m_max:
        return None
    return kg_min, kg_max, m_min, m_max


def caught_tab(texts):
    """the CAUGHT tab's tiles are showing (SHINY, LUCKY): the page isn't on INFO"""
    return {"SHINY", "LUCKY"} <= {ui.up(t) for t in texts}


def read_box(bounds):
    """drag the page up and read its box -> ('none' or the 4 values), or None: can't read it"""
    base.drag(0.5, 0.85, 0.5, 0.45, bounds, ms=500, settle=(0.6, 0.8), bring_front=False)
    for _ in range(6):
        screen, texts, path, bounds = base.settle(dex.look, lambda r: box(r[1]) not in (None, "low"), 2)
        got = box(texts)
        if got == "low":  # a long story above it
            base.drag(0.5, 0.8, 0.5, 0.5, bounds, ms=500, settle=(0.6, 0.8), bring_front=False)
            continue
        if got is None and not caught_tab(texts) and not has_label(texts):
            # a BATTLE-ONLY FORM note or a VIVILLON HABITAT box pushes the box further down (2026-11-12)
            base.drag(0.5, 0.8, 0.5, 0.4, bounds, ms=500, settle=(0.6, 0.8), bring_front=False)
            continue
        if got is None and caught_tab(texts) and tabs(texts):  # the page opened on CAUGHT: back to INFO
            log("  on the CAUGHT tab: tapping INFO")
            base.tap_box(tabs(texts), bounds, fuzz=0.006, rest=(1.2, 1.5))
            base.drag(0.5, 0.85, 0.5, 0.45, bounds, ms=500, settle=(0.6, 0.8), bring_front=False)
            continue
        return got
    return None


# ---------- the walk ----------

def region_of(n):
    """the region on the region list whose grid holds #n"""
    return next(name for name, first in reversed(REGIONS) if n >= first)


def to_start(start):
    """from anywhere to #start's page, INFO tab: its region on the region list, the nearest tile, then by title"""
    region = region_of(start)
    texts, bounds = dex.to_regions()
    dex.pick_page("POKÉMON")
    for i in range(5):  # the later regions are below the fold
        screen, texts, path, bounds = dex.look()
        if dex.tap_text(texts, bounds, lambda t: ui.up(t) == region):
            break
        if i == 4:
            base.keep_capture("region")
            raise Stop(f"can't find {region} on the region list")
        dex.swipe(0.5, 0.7, 0.5, 0.35, bounds)
    screen, texts, path, bounds = base.settle(dex.look, lambda r: r[0] == "grid" and dex.numbers(r[1]), 3)
    # (not the bottom row: the chip bar covers its tiles, and a tap there opens nothing, 2026-11-12)
    tiles = [(n, t) for n, t in dex.numbers(texts) if 0.2 < t[1] < dex.CHIP_Y - 0.1] if screen == "grid" else []
    if not tiles:
        base.keep_capture("grid")
        raise Stop(f"didn't get to {region}'s grid")
    n, tile = min(tiles, key=lambda nt: abs(nt[0] - start))
    dex.tap_at(tile[0] + tile[2] / 2, tile[1] - 0.04, bounds, wait=(2.0, 2.5))
    prev = None
    for _ in range(abs(n - start) + 6):  # the tap can land a tile off: walk to #start by the title
        screen, texts, path, bounds = base.settle(dex.look, lambda r: title(r[1]), 3)
        at = title(texts)
        if not at:
            base.keep_capture("page")
            raise Stop(f"tapped #{n} on the grid, but no species page opened")
        if at[0] == start or at[0] > start and prev is not None and prev < start:  # (no page for #start: the next)
            break
        prev = at[0]
        a, b = (SWIPE_NEXT[:2], SWIPE_NEXT[2:]) if at[0] < start else (SWIPE_NEXT[2:], SWIPE_NEXT[:2])
        base.drag(*a, *b, bounds, ms=300, settle=(0.8, 1.0), bring_front=False)
    else:
        raise Stop(f"can't get to #{start}'s page (at #{at[0]})")
    if at[0] != start:
        log(f"#{start} has no page here: starting at #{at[0]}")
    info = tabs(texts)
    if info:
        base.tap_box(info, bounds, fuzz=0.006, rest=(1.2, 1.5))
    return texts, bounds


def walk(acct, limit, done, start=1):
    texts, bounds = to_start(start)
    read, skipped, missed, last, stuck = 0, 0, [], None, 0
    while read < limit:
        screen, texts, path, bounds = base.settle(dex.look, lambda r: title(r[1]), 3)
        at = title(texts)
        if not at:
            base.keep_capture("title")
            raise Stop(f"lost the Pokédex page after #{last}")
        n, name = at
        if n == last:  # the swipe didn't move: the end, or a swipe that missed
            stuck += 1
            if stuck >= 2:
                log(f"#{n} is the last page")
                break
        else:
            stuck = 0
            if last and n != last + 1:
                log(f"  #{last} -> #{n}: the pages between aren't in the Pokédex (none seen)")
            if n in done:
                skipped += 1
            else:
                if not tabs(texts):  # a tab row still drawing: look again before calling it no tabs
                    texts = base.settle(dex.look, lambda r: tabs(r[1]), 1.5)[1]
                got = read_box(bounds) if tabs(texts) else "none"  # no tabs: a page for one never caught
                if got is None:
                    base.keep_capture(f"box-{n}")
                    log(f"  #{n} {name}: can't read MY RECORDS, passed over")
                    missed.append(n)
                else:
                    if not pokedb.save_record(acct, n, name, *(() if got == "none" else got)):
                        raise Stop("can't save to the database (POGO_DB off, or an error above)")
                    log(f"  #{n} {name}: " + ("no records" if got == "none" else
                                               f"{got[0]}-{got[1]} kg, {got[2]}-{got[3]} m"))
                read += 1
            last = n
        base.drag(*SWIPE_NEXT, bounds, ms=300, settle=(0.8, 1.0), bring_front=False)
    log(f"read {read} species, {skipped} read in the last {FRESH_HOURS} h passed by, last #{last}"
        + (f"; couldn't read {missed} (run again to try them)" if missed else ""))


def leave_dex():
    """a species page or the Pokédex's own screens: back out (home.start doesn't know them)"""
    for _ in range(6):
        screen, texts, path, bounds = dex.look()
        # (a page scrolled down has no title, only its tab row, 2026-11-12)
        if not (title(texts) or tabs(texts) or dex.numbers(texts) or screen in ("grid", "regions", "dex-search")):
            return
        ui.android.key("back")
        time.sleep(1.5)


def fresh(acct):
    """{dex: row} read in the last FRESH_HOURS"""
    now = time.time()
    return {n: r for n, r in pokedb.records(acct).items()
            if now - time.mktime(time.strptime(r["read_at"], "%Y-%m-%d %H:%M:%S")) < FRESH_HOURS * 3600}


def cmd_read(limit, again, start):
    session.ready()
    leave_dex()
    acct = home.trainer()
    dex.save_trainer(acct)
    pokedb.set_account(acct)
    done = {} if again else fresh(acct)
    if start is None:  # a rerun starts at the first species not read yet
        start = next((n for n in range(1, dex.LAST_DEX + 1) if n not in done), dex.LAST_DEX)
        if start > 1:
            log(f"#1-#{start - 1} read in the last {FRESH_HOURS} h: starting at #{start}")
    walk(acct, limit, done, start)


# ---------- the trades ----------

def trades(recs):
    """recs: {account: {dex: row}} -> the lines, giver first"""
    out = []
    a, b = ACCOUNTS
    for giver, taker in ((a, b), (b, a)):
        for n in sorted(set(recs.get(giver, {})) & set(recs.get(taker, {}))):
            g, t = recs[giver][n], recs[taker][n]
            for col, word, unit, sign, size in KINDS:
                if g[col] is None or t[col] is None or (g[col] - t[col]) * sign <= 0:
                    continue
                out.append(f"{giver} -> {taker}: #{n} {g['name']} {word} {g[col]} {unit} beats {t[col]} {unit}"
                           f"  (search on {giver}: {n}&{size})")
    return out


def cmd_compare():
    recs = {acct: pokedb.records(acct) for acct in ACCOUNTS}
    for acct in ACCOUNTS:
        print(f"{acct}: {len(recs[acct])} species read")
    lines = trades(recs)
    print("\n".join(lines) if lines else "no record either account could beat by a trade")
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="compare")
    with open(os.path.join(base.RUN_DIR, "trades.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("read", "compare"))
    ap.add_argument("--limit", type=int, default=10 ** 9)
    ap.add_argument("--again", action="store_true", help="read species read in the last hours too")
    ap.add_argument("--from", dest="start", type=int, help="start at this Pokédex number")
    a = ap.parse_args()
    if a.cmd == "compare":
        return cmd_compare()
    if not ui.ANDROID:
        sys.exit("Android only for now: POGO_PHONE=android")
    if a.start is not None and not 0 < a.start <= dex.LAST_DEX:
        ap.error(f"--from takes 1-{dex.LAST_DEX}")
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="sizerecords")
    session.main(cmd_read, a.limit, a.again, a.start)


if __name__ == "__main__":
    main()
