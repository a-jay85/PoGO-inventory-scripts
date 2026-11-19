#!/usr/bin/env python3
"""Fills the Pokémon database (../shared/pokedb.py) with the IVs of one search's Pokémon: the ones it doesn't know
yet get opened and appraised. Nothing is tagged or changed in the game.

  POGO_PHONE=android caffeinate -dimsu python3 dbfill.py [--search Q] [--limit N]   the Pixel
  caffeinate -dimsu python3 dbfill.py [--search Q] [--limit N]                      the iPhone, through iPhone Mirroring
  pogo.py dbfill [--search Q] [--limit N]                                           the same, through the front door

--search Q: the storage search, `4*` (every 100%) when not given. Keep it tight: every result's page is looked at.
--limit N: appraise at most N.

It opens the first result and swipes on through the rest. Each page's top read goes into the database as it does
in every script (base.steady_detail). A page the database already has IVs for (same weight, height, CP and HP) is
swiped past. The rest are appraised, and their IVs and species are learned (base.exact_ivs).
Only targeted searches: the user ruled out opening all of storage for the database at once.
Log in runs/<time>-dbfill/.
"""
import os, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import base
from base import Skip, log
import home, pokedb, search, session, ui
from taps import details

DEFAULT = "4*"


def known(info):
    """the database already has this page's IVs: one record of the same Pokémon (weight, height, CP, HP) with them"""
    who = base.OPENED.get("who")
    if not who or info["cp"] is None or info["hp"] is None:
        return False
    return any(r.get("atk") is not None and base.same_pokemon(who, (r["cp"], r["hp"], r["kg"], r["m"]))
               for r in pokedb.find(cp=info["cp"], hp=info["hp"]))


def fill_one(info, texts):
    """appraise the open page; the database learns its IVs. Leaves the detail page open. -> the IVs"""
    sp = ui.species_for(info["name"], info["texts"]) or base.species_from_candy(texts, info["cp"], info["hp"])
    base.open_appraisal()
    try:
        bars, raws = base.appraise()
        return base.exact_ivs(sp, info["cp"], info["hp"], bars, raws)
    finally:
        base.go("dialog", "detail")


def script(query, limit):
    home.start()  # opens the phone (iPhone Mirroring or the Pixel) and takes its lock, as every script does
    who = home.trainer()
    search.to_search_list()  # (trainer() can end on the map)
    texts = search.start_search(query)[1]
    if not ui.tiles(texts):
        log(f"no Pokémon in {query}")
        return
    n = {"seen": 0, "known": 0, "filled": 0, "passed": 0}
    t_start = time.time()

    def read():
        base.OPENED.clear()  # (a new Pokémon on the page: steady_detail's first read is it, and learns its who)
        info, texts, _ = base.steady_detail()
        if info["cp"] is None:  # right after a swipe the CP sparkles in and can read blank (Pixel, Chansey, 2026-11-19)
            base.settle(lambda: ui.detail_info(base.wait_for("detail")[1]), lambda i: i["cp"] is not None, 2)
            base.OPENED.clear()
            info, texts, _ = base.steady_detail()
        return info, texts, None  # (None: next_one reads the bounds before each swipe)

    # (seen by weight and height too: three 100 Chansey at CP1255 396HP ended the walk at the second, 2026-11-19)
    for info, texts, _, seen in details(key=base.who, read=read, poll=search.POLL, reswipe=True):
        n["seen"] += 1
        if known(info):
            n["known"] += 1
            continue
        if n["filled"] >= limit:
            log(f"--limit {limit} reached")
            break
        t0 = time.time()
        try:
            ivs = fill_one(info, texts)
            n["filled"] += 1
            log(f"  {info['name']} CP{info['cp']}: {'/'.join(map(str, ivs))}  ({time.time() - t0:.1f}s)")
        except Skip as e:
            n["passed"] += 1
            log(f"  {info['name']} CP{info['cp']}: passed ({e})")
    base.back_to_list()
    log(f"{who}, {query}: {n['seen']} looked at, {n['known']} known already, {n['filled']} appraised, "
        f"{n['passed']} passed, {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    a = sys.argv[1:]
    q = a[a.index("--search") + 1] if "--search" in a and a.index("--search") + 1 < len(a) else DEFAULT
    rest = [x for i, x in enumerate(a) if not (x == "--search" or (i and a[i - 1] == "--search"))]
    if any(x != "--limit" and not x.isdigit() for x in rest):
        sys.exit(__doc__)
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="dbfill")
    session.main(script, q, session.limit(rest))
