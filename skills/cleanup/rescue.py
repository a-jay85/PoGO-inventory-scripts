#!/usr/bin/env python3
"""Cleanup: find 98%+ Pokémon that got Nope by mistake, and keep them (star on, Nope off).

  caffeinate -dimsu python3 rescue.py [--limit N] [--dry-run]
  POGO_PHONE=android caffeinate -dimsu python3 rescue.py ...   (Android phone over USB)

A wrong name ('FP*' on a 98% lucky) could land a 98% one in Nope. 98%+ means two stats at 15, so two of
4attack/4defense/4hp hold: that's the first search. A shadow is 98%+ once purified from 12/13/13 (84%), so shadows
get their own search, #Nope&shadow&3*,4* (3* is 82-98%). It opens each one and appraises it. 98%+ (a shadow: once purified) gets the star and loses Nope; its other tags stay. The rest are
left alone. --dry-run appraises and logs, changes nothing. Log in runs/<time>/.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import run as base
from run import Stop, Skip, log, go, front
import search

QUERIES = ("#Nope&!shadow&4attack,4defense&4attack,4hp&4defense,4hp",  # two of the three at 15
           "#Nope&shadow&3*,4*")


def main(limit, dry):
    kept, looked = [], [0]

    def visit(i, n, c):
        base.open_tile(i)
        info, _, _ = base.steady_detail()
        bare = dict(info, name=(info["name"] or "").replace(" ", ""))  # OCR drops or adds spaces: '91H' / '91 H'
        if not base.opened_right(bare, n.replace(" ", ""), c):
            raise Skip(f"opened {info['name']!r} but tile said {n!r}")
        if not any(base.is_tag(t, "Nope") for t in info["tags"]):
            raise Skip(f"no Nope tag on detail: {info['tags']}")
        keep, _, _, what = base.high_iv()
        looked[0] += 1
        if not keep:
            log(f"  {n} CP{c}: {what}, under 98%")
            go("close", "list")
            return False
        if dry:
            log(f"DRY would keep {n} CP{c}: {what}")
            go("close", "list")
            return False
        base.set_star(True)
        base.set_tags(off=["Nope"])
        kept.append({"name": n, "cp": c, "ivs": what})
        base.save("kept.json", kept)
        log(f"DONE kept {n} CP{c}: {what}, star on, Nope off")
        go("close", "list")
        return True

    for q in QUERIES:
        if looked[0] >= limit:
            break
        log(f"--- {q}")
        search.start_search(q)
        search.walk_list(visit, limit - looked[0])
    log(f"appraised {looked[0]}, kept {len(kept)}: {[(k['name'], k['cp'], k['ivs']) for k in kept]}")


if __name__ == "__main__":
    a = sys.argv[1:]
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 10 ** 9
    base.new_run_dir(os.path.join(HERE, "runs"))
    try:
        front()
        main(limit, "--dry-run" in a)
    except Stop as e:
        log(f"STOP: {e}")
        sys.exit(1)
    finally:
        log(f"run folder: {base.RUN_DIR}")
