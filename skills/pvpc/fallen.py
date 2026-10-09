#!/usr/bin/env python3
"""Fallen out: older Pokémon that newer, better ones push out of the top. Shared by /ivcsort and /pvpc.

Each skill finds its own fallen-out ones and saves them in <run dir>/fallen.json, one entry per Pokémon:
{"name", "cp", "dex": [dex numbers it could be], "why": [...]}. This file decides what happens to them next:
  not traded + caught 2016-2020 -> tag GuaranteedLucky (a trade is guaranteed lucky)
  not traded + older than OLD_DAYS -> tag Old
  anything else (traded: a Pokémon trades only once, or newer) -> star off + Nope
Shiny and costume ones are never touched. groups() sorts them with in-game searches (reads only). act() opens each
one, asks the skill to judge it again on its own detail screen, then tags it.
"""
from collections import Counter

import run as base
from run import log, go
import search

OLD_DAYS = 300
GROUPS = [("GuaranteedLucky", "&!traded&year2016-2020"), ("Old", f"&!traded&age{OLD_DAYS + 1}-"),
          ("Nope", f"&traded,age0-{OLD_DAYS}")]  # in this order: each tag drops out of the later searches
BASE = "&!#Nope&!#IVC&!shiny&!costume&!#Old&!#GuaranteedLucky"
CHUNK = 20  # dex numbers per search


def searches(fallen):
    dexes = sorted({d for f in fallen for d in f["dex"]})
    chunks = [dexes[i:i + CHUNK] for i in range(0, len(dexes), CHUNK)]
    return [(g, ",".join(map(str, ch)) + BASE + extra) for g, extra in GROUPS for ch in chunks]


def groups(iv_only=True):
    """read-only: type each group search, note which fallen-out tiles show up in it -> fallen-groups.json.
    iv_only: the names start with a number, so a list sorted by name can stop at the first plain name."""
    fallen = base.load("fallen.json")
    want = Counter((f["name"], f["cp"]) for f in fallen)
    out = {g: {} for g, _ in GROUPS}
    taken = Counter()
    base.front()
    for g, q in searches(fallen):
        got, _ = search.run_search(q, iv_only=iv_only)
        hits = [(n, c) for n, c in got if want[(n, c)]]
        free = Counter(hits)
        for k in free:  # an earlier group took it: the tag it gets keeps it out of this search
            free[k] = min(free[k], want[k] - taken[k])
        mine = [list(k) for k, v in free.items() for _ in range(v)]
        taken.update(map(tuple, mine))
        out[g][q] = mine
        log(f"  {g}: {len(mine)} fallen-out in {q}")
    base.save("fallen-groups.json", out)
    for g in out:
        log(f"{g}: {sum(len(v) for v in out[g].values())}")
    return out


def summary(fallen, grouped):
    """lines for the plan / fallen.txt"""
    lines = [f"FALLEN OUT: {len(fallen)} older Pokémon now outside the top. Grouped GuaranteedLucky / Old / Nope; "
             "act-fallen checks each one again on its detail screen first."]
    lines += [f"  {f['name']!r:16} CP{f['cp']:<5} {f.get('what', '')}: {'; '.join(f['why'])}" for f in fallen]
    if grouped:
        lines += ["", "FALLEN OUT, by group:"] + [f"  {g}: {sum(len(v) for v in grouped[g].values())}" for g in grouped]
    return lines


def act(limit, recheck, off=(), stop=None, odd=None):
    """tag the grouped ones. recheck(name, cp) runs on the open detail screen and leaves it there:
    -> (still fallen?, what to log). off: tags to untick at the same time"""
    grouped = base.load("fallen-groups.json")
    done = Counter()
    for g, q in searches(base.load("fallen.json")):
        todo = Counter(map(tuple, grouped[g].get(q, [])))
        if not todo or sum(done.values()) >= limit:
            continue
        log(f"fallen {g}: {sum(todo.values())} in {q}")

        def visit(i, n, c):
            if not todo[(n, c)] or sum(done.values()) >= limit:
                return False
            base.open_tile(i)
            falls, what = recheck(n, c)
            todo[(n, c)] -= 1
            if not falls:
                log(f"  {n} CP{c}: {what} on a closer look, leaving it")
                go("close", "list")
                return False
            ivs = raws = None
            if g == "Nope":  # appraise before the star comes off: 98%+ never gets Nope
                keep, ivs, raws, what = base.high_iv()
                if keep:
                    log(f"  {n} CP{c}: appraised {what}, 98%+ never gets Nope, leaving it")
                    go("close", "list")
                    return False
                base.set_star(False)
            base.set_tags(on=[g], off=off, ivs=ivs, raws=raws)
            done[g] += 1
            log(f"DONE fallen {g} {n!r} CP{c}: {what}")
            go("close", "list")
            return True

        search.start_search(q)
        search.walk_list(visit, stop=stop, odd=odd)
    log(f"fallen done: {dict(done)}")
    return done
