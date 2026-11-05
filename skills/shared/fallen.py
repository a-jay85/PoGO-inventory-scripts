#!/usr/bin/env python3
"""Fallen out: older Pokémon that newer, better ones push out of the top. Shared by /ivc and /pvpc.

Each skill finds its own fallen-out ones and saves them in <run dir>/fallen.json, one entry per Pokémon:
{"name", "cp", "dex": [dex numbers it could be], "why": [...]}. This file decides what happens to them next:
  not traded + caught 2016-2020 -> tag GuaranteedLucky (a trade is guaranteed lucky)
  not traded + older than OLD_DAYS -> tag Old
  anything else (traded: a Pokémon trades only once, or newer) -> its final tag at the door (door.py: star off, name
  cleared), or left as it is on door's not-sure list
  shiny -> always the door, never GuaranteedLucky or Old (verdict.shiny: default name and a star; traded, its tags come
  off; untraded, Remote Trade and RT. The user's rule, 2026-11-03). Its own group, so each search still says shiny or not
A costume one always goes to the door (it names and stars one at 93%+, the user's rule,
2026-11-02), never straight to GuaranteedLucky or Old. groups() sorts them with in-game searches (reads only). act() opens each
one, asks the skill to judge it again on its own detail screen, then tags it and clears its name.
A door one that appraises 98%+ is left alone. (The group is still called "Nope" in fallen-groups.json.)
"""
from collections import Counter

import os, sys
HERE = os.path.dirname(os.path.realpath(__file__))
import base
from base import log, go
import search

OLD_DAYS = 300
GROUPS = [("GuaranteedLucky", "&!shiny&!traded&!costume&!xxl&year2016-2020"),
          ("Old", f"&!shiny&!traded&!costume&!xxl&age{OLD_DAYS + 1}-"),
          ("Nope", f"&!shiny&traded,age0-{OLD_DAYS},costume,xxl"),  # (xxl: the door makes it a favorite, at any age)
          ("Shiny", "&shiny")]  # in this order: each tag drops out of the later searches
DOOR_GROUPS = ("Nope", "Shiny")  # judged at the door
READ_ORDER = ("Nope", "Shiny", "GuaranteedLucky", "Old")  # most fall-outs are traded or new. Nope and Shiny share no
# Pokémon with the other two, so these can be read first; GuaranteedLucky must stay ahead of Old, which holds it all
BASE = "&!#IVC&!#Old&!#GuaranteedLucky"
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
    for g, q in sorted(searches(fallen), key=lambda s: READ_ORDER.index(s[0])):
        dexes = set(map(int, q.split("&")[0].split(",")))
        # a Pokémon is in one group only: once all of a search's dex numbers are placed, it can't find anything new
        if not any(taken[k] < want[k] and dexes & set(f["dex"]) for f in fallen for k in [(f["name"], f["cp"])]):
            log(f"  {g}: every fallen-out one it could hold is placed, not typed: {q}")
            continue
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
    lines = [f"FALLEN OUT: {len(fallen)} older Pokémon now outside the top. Grouped GuaranteedLucky / Old / Nope / Shiny; "
             "each one is checked again on its detail screen first."]
    lines += [f"  {f['name']!r:16} CP{f['cp']:<5} {f.get('what', '')}: {'; '.join(f['why'])}" for f in fallen]
    if grouped:
        lines += ["", "FALLEN OUT, by group:"] + [f"  {g}: {sum(len(v) for v in grouped[g].values())}" for g in grouped]
    return lines


def act(limit, recheck, tag, species, off=(), odd=None, gym_top20=None, iv_top=lambda n, c: None, pure_top=None,
        who=None):
    """tag the grouped ones. recheck(name, cp) runs on the open detail screen and leaves it there:
    -> (still fallen?, what to log). species(name, cp) on that screen -> its species ids, for the door. tag: the
    skill's (IVC / PvpC), for the door's not-sure list. off: tags to untick at the same time. gym_top20: what
    recheck's rules already say of a gym defender (/ivc: False, its NOPE covers the gym rule). who: the signed-in
    trainer, when known (saves the door a look). iv_top(name, cp)
    after recheck: a lucky one's rank in its line (verdict.Facts), None when recheck doesn't know it"""
    grouped = base.load("fallen-groups.json")
    done, account = Counter(), [who]
    for g, q in searches(base.load("fallen.json")):
        todo = Counter(map(tuple, grouped.get(g, {}).get(q, [])))  # (a run grouped before Shiny has none)
        if not todo or sum(done.values()) >= limit:
            continue
        log(f"fallen {g}: {sum(todo.values())} in {q}")
        gate = None
        if g in DOOR_GROUPS:  # one Door per search: its searches read what the page can't show, within this one
            import door  # (here: door loads verdict, which loads /ivc, which loads this)
            gate = door.Door(tag, scope=q, account=account[0])
            account[0] = gate.account
            for k, v in gate.listed().items():
                if todo[k]:
                    log(f"  {k[0]} CP{k[1]}: on the not-sure list, passed over")
                    todo[k] -= min(v, todo[k])

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
            if g in DOOR_GROUPS:  # appraise first: 98%+ never goes
                keep, ivs, raws, iv = base.high_iv()
                if keep:
                    log(f"  {n} CP{c}: appraised {iv}, 98%+ never goes, leaving it")
                    go("close", "list")
                    return False
                info, texts, _ = base.steady_detail()
                got = gate.judge(info, texts, species(n, c), ivs, (n, c), size=base.extras(texts)[2], raws=raws,
                                 gym_top20=gym_top20, clear=True, unstar=True, iv_top=iv_top(n, c), pure_top=pure_top)
                done[got] += 1
                log(f"DONE fallen door {got} {n!r} CP{c}: {what}")
                go("close", "list")
                # a cleared name leaves the IV / Pvp names (a list sorted by Name). Left as it is, it stays
                return got == "tag"
            base.set_tags(on=[g], off=off)
            done[g] += 1
            base.clear_name()  # an old /ivc or Pvp name would make /ivc pass over it
            log(f"DONE fallen {g} {n!r} CP{c}: {what}, name cleared")
            go("close", "list")
            return True

        search.start_search(q)
        # ends when every one wanted here is done: the list's order can't be trusted (a plain name can come first)
        search.walk_list(visit, stop=lambda n: not +todo or sum(done.values()) >= limit, odd=odd)
    log(f"fallen done: {dict(done)}")
    return done
