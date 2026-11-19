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
swiped past. The rest are appraised, and their IVs and species are learned (base.exact_ivs). A nickname whose candy
and types don't tell the species: the appraisal's 'This ... was caught' line does. A CP that doesn't read (art or the
Pokémon over it): the power-up dialog shows it on plain white (opened and cancelled, nothing spent). No POWER UP
there (level 50): the bars are checked against the HP instead (base.ivs_by_hp).
Only targeted searches: the user ruled out opening all of storage for the database at once.
Log in runs/<time>-dbfill/.
"""
import os, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import base
from base import Skip, log
import home, pokedb, powerup, pvp, search, session, ui
from taps import Pass, details

DEFAULT = "4*"


def known(info):
    """the database already has this page's IVs: one record of the same Pokémon (weight, height, HP, and CP when it
    read) with them. By weight, height and HP, as pokedb matches: a CP that didn't read still finds it"""
    who = base.OPENED.get("who")
    if not who or None in who[1:]:
        log(f"  {info['name']}: HP {who and who[1]}, {who and who[2]} kg, {who and who[3]} m read: can't look it up")
        base.keep_capture("no kg or m")
        return False
    return any(r.get("atk") is not None and base.same_pokemon(who, (r["cp"], r["hp"], r["kg"], r["m"]))
               for r in pokedb.find(hp=who[1], kg=round(who[2], 2), m=round(who[3], 2)))


def species(info, texts):
    """the name, else the candy line and types. A CP no form there can have is a misread (CP25450, CP24): then the
    HP alone picks. -> (species or None, the CP to trust or None)"""
    cp = info["cp"]
    sp = ui.species_for(info["name"], info["texts"])
    if sp:
        return sp, fits(sp, cp, info["hp"])
    try:
        return base.species_from_candy(texts, cp, info["hp"]), cp
    except Skip as e:
        if cp is None:
            log(f"  {e}: asking the appraisal")
            return None, None
    try:
        sp = base.species_from_candy(texts, None, info["hp"])
        log(f"  CP{cp} fits none of them: a misread, left out")
        return sp, None
    except Skip as e:
        log(f"  {e}: asking the appraisal")
        return None, cp  # (the appraisal's species checks it)


def fits(sp, cp, hp):
    """cp if some form of sp can have it with this HP, else None (a misread)"""
    if cp is None or any(base.can_have(s, cp, hp) for s in sp if s in pvp.SPECIES):
        return cp
    log(f"  CP{cp} fits none of {sp}: a misread, left out")
    return None


def fill_one(info, texts):
    """appraise the open page; the database learns its IVs. A name and candy that don't tell the species: the
    appraisal's 'This Annihilape was caught' line does. A CP that didn't read is read off the power-up dialog, else the bars are checked against the HP at the levels the power-up cost allows.
    Leaves the detail page open. -> the IVs"""
    sp, cp = species(info, texts)
    levels = None if cp is not None else powerup.cost_levels(texts, info["cp"])[1] or None
    base.open_appraisal()
    try:
        if not sp:
            sp = base.appraisal_species(info["texts"])
            cp = fits(sp, cp, info["hp"])
        bars, raws = base.appraise()
    finally:
        base.go("dialog", "detail")
    if cp is None:
        cp = dialog_cp(info, sp)
    if cp is None:
        return base.ivs_by_hp(sp, info["hp"], bars, raws, levels)
    return base.exact_ivs(sp, cp, info["hp"], bars, raws)


def dialog_cp(info, sp):
    """the CP off the power-up dialog (opened and cancelled), into the database. None: no POWER UP (level 50)"""
    try:
        cp = powerup.dialog_cp(info, lambda c: any(base.can_have(s, c, info["hp"]) for s in sp if s in pvp.SPECIES))
    except Pass as e:
        log(f"  no CP from the power-up dialog: {e}")
        return None
    who = base.OPENED.get("who")
    if who:
        base.OPENED["who"] = (cp, *who[1:])
        pokedb.seen(base.OPENED["who"])
    return cp


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
        def steady():
            base.OPENED.clear()  # (a new Pokémon on the page: steady_detail's first read is it, and learns its who)
            return base.steady_detail()
        # right after a swipe the CP sparkles in and can read blank (Pixel, Chansey, 2026-11-19): read it again
        info, texts, _ = base.settle(steady, lambda r: r[0]["cp"] is not None, 3)
        if info["cp"] is None:
            base.keep_capture("no CP")
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
