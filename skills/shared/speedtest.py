#!/usr/bin/env python3
"""Go through a step's motions on the phone and time them, changing nothing: for speed work, where the logic isn't
what's tested (the user, 2026-11-17). Each round opens a tile of the full list, does the step, and backs out.

  POGO_PHONE=android caffeinate -dimsu python3 speedtest.py tags [<tag>] [--n 3]
        menu, TAG, scroll the sheet to the <tag> row (default Fallen) and get it ready to tap, then out by the X
        (nothing saved). The rounds after the first find the row the way a run does: from where it was seen
  POGO_PHONE=android caffeinate -dimsu python3 speedtest.py cost [--n 3]
        the door's page bottom and back (caught date, Candy XL), then its power-up cost read, as door.facts() does
  SHARED=<another checkout's skills/shared> ... : time that checkout's code instead (the before of a change)
"""
import os, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.environ.get("SHARED", HERE))
import base, ui, search, session
from base import log, go


def tags(T, n):
    took = []
    for i in range(n):
        base.open_tile(i + 1)  # (tiles count from 1)
        base.steady_detail()
        t0 = time.time()
        go("menu", "menu")
        go("TAG", "tags")
        if base.show_tag(ui.norm(T)) is None:
            base.cancel_tags()
            rows = sorted(base.TAG_AT, key=base.TAG_AT.get)
            raise base.Stop(f"no {T} tag on this account. Its rows, top to bottom: {rows}")
        if ui.ANDROID:
            base.lift_tag_row(ui.norm(T))
        took.append(time.time() - t0)
        log(f"  round {i + 1}: menu to the {T} row ready to tap: {took[-1]:.1f}s")
        base.cancel_tags()
        base.back_to_list()
    log(f"tags: {', '.join(f'{t:.1f}' for t in took)} s (first round finds the row from scratch)")


def cost(n):
    import door, powerup, tagsheet
    door.powerup, door.tagsheet = powerup, tagsheet  # (Door() sets these; its page_bottom needs no Door)
    took = []
    for i in range(n):
        base.open_tile(i + 1)
        info, texts, _ = base.steady_detail()
        t0 = time.time()
        door.Door.page_bottom(None, info)
        t1 = time.time()
        got = door.cost_levels(texts, info["cp"])
        took.append((t1 - t0, time.time() - t1))
        log(f"  round {i + 1}: page bottom and back {took[-1][0]:.1f}s, cost read {took[-1][1]:.1f}s: {got}")
        base.back_to_list()
    log(f"cost: page bottom {', '.join(f'{a:.1f}' for a, _ in took)} s; cost read {', '.join(f'{b:.1f}' for _, b in took)} s")


def main(a):
    n = int(a[a.index("--n") + 1]) if "--n" in a else 3
    words = [w for w in a[1:] if not w.startswith("--") and w != str(n)]
    base.start()
    search.to_search_list()
    if a[0] == "tags":
        tags(words[0] if words else "Fallen", n)
    elif a[0] == "cost":
        cost(n)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="speedtest")
    session.main(main, sys.argv[1:])
