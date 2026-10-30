#!/usr/bin/env python3
"""The not-sure list's lucky ones (../shared/runs/not-sure.json): rank each against its line, then the door.

  POGO_PHONE=android caffeinate -dimsu python3 lucky.py [--limit N] [--look]

The user's rule (2026-10-30), traded or not (verdict.lucky):
1. in the top 5 IV of its line's non-shadow ones (normal, lucky, purified, Dynamax), 6 if the line can mega evolve:
   star on. /ivcsort's searches and spots, but a weak line gets its 5/6 too. A tie with last place keeps.
2. out of that, a PvP top-100 IV (pvp.make_name): PvpC on, /pvpc compares it with the ones you own.
3. the rest: name cleared, one or two power-ups if that reaches a higher Candy XL tier, Transfer.
Per species it types /ivcsort's searches for the line once (they leave out #Nope, so a Nope-tagged lucky one is never
its own rival). A search that showed no tiles and no count leaves that species as it is. Then it walks #<tag>&lucky
and sends each listed one to the door with what step 1 found. --look ranks and changes nothing.
"""
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
sys.path.insert(0, os.path.join(HERE, "..", "ivcsort"))
import ui, base, search, session, door, home
from base import Skip, log, go
import sort


def listed(who):
    """the not-sure list's lucky ones on this account, one species each"""
    return [e for e in door.load_list() if e["account"] == who and "lucky" in e["why"] and len(e["species"]) == 1
            and len(e["ivs"]) == 3]


def drop(tag, n, c, who):
    """a judged one off the not-sure list"""
    got = door.load_list()
    i = next((i for i, e in enumerate(got) if (e["tag"], e["tile"], e["cp"], e["account"]) == (tag, n, c, who)), None)
    if i is not None:
        del got[i]
        json.dump(got, open(door.NOT_SURE, "w"), indent=1, ensure_ascii=False)


def rank(entries):
    """-> {(tag, tile name, CP): True (top IV), False, or None (a search didn't run)}"""
    results, out = {}, {}
    for e in entries:
        sid, k = e["species"][0], (e["tag"], e["tile"], e["cp"])
        qs = [q for q, _, _ in sort.groups(sid, "plain")]
        for q in qs:
            if q not in results:
                got, want = search.run_search(q, True, edit=True)
                if not got and want is None:  # no tiles and no count: the search didn't run
                    got, want = search.run_search(q, True)
                results[q] = None if not got and want is None else got
                log(f"  {q}: {'did not run' if results[q] is None else f'{len(got)} tiles'}")
        if any(results[q] is None for q in qs):
            out[k] = None
            log(f"RANK {e['tile']!r} CP{e['cp']} {sid}: a search didn't run, left as it is")
            continue
        m = {"species": sid, "cp": e["cp"], "name": e["tile"], "shadow": False, "lucky": True, "dynamax": False}
        mine = sum(e["ivs"])
        r = sort.by_iv(sid, e["tile"], sort.my_reach(m, mine, results, "plain"))
        out[k], why, _ = sort.judge_pool(m, results, "plain", "lucky", mine, r, me_in_pool=False, full=True)
        log(f"RANK {e['tile']!r} CP{e['cp']} {sid}: {'top IV' if out[k] else 'out'} ({why})")
    return out


def walk(tag, ranks, limit, counts, who):
    """#tag&lucky: each one ranked gets the door"""
    scope = f"#{tag}&lucky"
    gate = door.Door(tag, scope=scope, account=who)
    todo = Counter({(n, c): 1 for (t, n, c), v in ranks.items() if t == tag and v is not None})

    def visit(i, n, c):
        if not todo[(n, c)]:
            return False
        todo[(n, c)] -= 1
        base.open_tile(i)
        counts["opened"] += 1
        info, texts, _ = base.steady_detail()
        if not base.opened_right(info, n, c):
            raise Skip(f"opened {info['name']!r} but tile said {n!r}")
        _, ivs, raws, iv = base.high_iv()
        sp = ui.species_for(info["name"], info["texts"]) or base.species_from_candy(texts, info["cp"] or c, info["hp"])
        info, texts, _ = base.steady_detail()
        got = gate.judge(info, texts, sp, ivs, (n, c), size=base.extras(texts)[2], raws=raws, clear=True,
                         iv_top=ranks[(tag, n, c)])
        counts[got] = counts.get(got, 0) + 1
        log(f"DONE lucky door {got} {n!r} CP{c} {iv}")
        go("close", "list")
        if got != door.UNSURE:  # (a new not sure one replaced its old entry already)
            drop(tag, n, c, who)
        return got != door.UNSURE  # (the rest lost the tag: off the list)

    search.start_search(scope)
    search.walk_list(visit, stop=lambda n: counts["opened"] >= limit)


def main(limit, look):
    base.front()
    who = home.trainer()  # once, first: it ends on the map
    home.start()  # back to the Pokémon screens
    entries = listed(who)
    log(f"not-sure list: {len(entries)} lucky ones on {who}")
    if not entries:
        return
    search.to_search_list()
    ranks = rank(entries)
    log(f"ranked: {Counter(map(str, ranks.values()))}")
    if look:
        return
    counts = {"opened": 0}
    for tag in dict.fromkeys(e["tag"] for e in entries):
        if counts["opened"] < limit:
            walk(tag, ranks, limit, counts, who)
    log(f"lucky done: {counts}")


def script(a):
    base.start()
    main(session.limit(a), "--look" in a)


if __name__ == "__main__":
    base.new_run_dir(os.path.join(HERE, "runs"))
    session.main(script, sys.argv[1:])
