#!/usr/bin/env python3
"""Deletes from the Pokémon database (../shared/pokedb.py) the ones a bulk tagger tagged Transfer without opening
them (savedsearch.tag_pile). Nothing is tagged or changed in the game.

  POGO_PHONE=android caffeinate -dimsu python3 dbsweep.py [--limit N]   the Pixel
  caffeinate -dimsu python3 dbsweep.py [--limit N]                      the iPhone, through iPhone Mirroring
  pogo.py dbsweep                                                       the same, through the front door

It searches #Transfer and reads the tiles, screen by screen. A tile whose name and CP fit one record deletes that
record, with no tap. Only when two records fit does it open the tile: the page's top (weight, height, CP, HP) tells
them apart, and its Transfer chip deletes the right one. It never drags down a page. --limit N opens at most N.
A tile that fits no record is passed over: it was never opened, so it was never in the database.

A record is one the scripts opened before, so a tile with the same name and CP is almost always it. If it isn't (a
never-opened twin got the tag), the record goes anyway: the database is rebuilt from the next look at that one.
Log in runs/<time>-dbsweep/.
"""
import os, sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import base
from base import log
import home, pokedb, search, session
from rules import TRANSFER
from tagsheet import search_exact
from taps import settled_tiles


def fits(rows, name, cp):
    """the records a tile could be: same CP, and the tile's name (cut short on long nicknames) starts the record's"""
    t = base.short(name)
    return [r for r in rows if r["cp"] == cp and t and base.short(r["nickname"]).startswith(t)]


def script(limit):
    who = home.trainer()
    rows = pokedb.find(who)
    if not rows:
        log(f"no {who} Pokémon in the database: nothing to sweep")
        return
    search.to_search_list()  # (trainer() can end on the map)
    search_exact(f"#{TRANSFER}")
    if not settled_tiles():
        log(f"nothing tagged {TRANSFER}")
        return
    counts = {"deleted": 0, "opened": 0}
    done = set()  # (name, CP) acted on: walk_list asks again on each screen

    def want(name, cp):
        if (name, cp) in done:
            return False
        got = fits(rows, name, cp)
        if not got:
            if near := [r["nickname"] for r in rows if r["cp"] == cp]:  # a misread name keeps its record: say so
                log(f"  {name!r} CP{cp}: the CP fits {near}, the name doesn't: left")
                done.add((name, cp))
            return False
        done.add((name, cp))
        if len(got) == 1:  # one fits: delete it, no need to open
            r = got[0]
            pokedb.gone((r["cp"], r["hp"], r["kg"], r["m"]), f"#{TRANSFER} tile {name} CP{cp}")
            rows.remove(r)
            counts["deleted"] += 1
            return False
        if counts["opened"] >= limit:
            log(f"  {name} CP{cp}: {len(got)} records fit, --limit reached: left")
            return False
        log(f"  {name} CP{cp}: {len(got)} records fit: opening it")
        return True

    def visit(i, name, cp):
        base.open_checked(i, name, cp, name_ok=True)  # its steady read sees the Transfer chip: pokedb deletes it
        counts["opened"] += 1
        rows[:] = pokedb.find(who)
        base.back_to_list()
        return False

    search.walk_list(visit, want=want)
    log(f"done: {counts['deleted']} deleted from tiles, {counts['opened']} opened to tell twins apart, "
        f"{len(rows)} {who} Pokémon left in the database")


if __name__ == "__main__":
    a = sys.argv[1:]
    if any(x != "--limit" and not x.isdigit() for x in a):
        sys.exit(__doc__)
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="dbsweep")
    session.main(script, session.limit(a))
