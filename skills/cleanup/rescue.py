#!/usr/bin/env python3
"""Cleanup: find 98%+ Pokémon that got Nope by mistake, and keep them (star on, Nope off).

  caffeinate -dimsu python3 rescue.py [--limit N] [--dry-run]
  POGO_PHONE=android caffeinate -dimsu python3 rescue.py ...   (Android phone over USB)

A wrong name ('FP*' on a 98% lucky) could land a 98% one in Nope. Only 3* (82-98%) and 4* (100%) can be 98%+,
a shadow too once purified (2* tops out at 80%, 93% purified). So it searches #Nope&3*,4*, opens each one and
appraises it. 98%+ (a shadow: once purified) gets the star and loses Nope; its other tags stay. The rest are
left alone. --dry-run appraises and logs, changes nothing. Log in runs/<time>/.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import run as base
from run import Stop, Skip, log, go, front
import search

QUERY = "#Nope&3*,4*"


def main(limit, dry):
    kept, looked = [], [0]

    def visit(i, n, c):
        base.open_tile(i)
        info, _, _ = base.steady_detail()
        if not base.opened_right(info, n, c):
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

    search.start_search(QUERY)
    search.walk_list(visit, limit)
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
