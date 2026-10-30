#!/usr/bin/env python3
"""The last Nope pile: one pass that gives every Pokémon still tagged Nope its final tag, the way /ivc and /pvpc do now
(../shared/door.py). Nothing tags Nope any more. Run it once on each account.

  POGO_PHONE=android caffeinate -dimsu python3 nopes.py [--limit N] [--dry-run]

1. Nope comes off the ones that already have their final tag (an old `tradeable.py tag --nope` that stopped before
   its last step left Nope on next to it).
2. Walks #Nope. Each one is opened and appraised:
   - 98%+ (a shadow: once purified): star on, Nope off. It never goes.
   - may still be a keeper: 93%+, a nickname (an old /ivc or Pvp name, XXL ...), or a gym defender (top 20 CP or
     IV can't be checked here): name cleared, IVC on, Nope off. /ivc names it again and /ivcsort or /pvpc judges it
     with today's rules, door and all.
   - also has IVC or PvpC: Nope off, that skill decides.
   - the rest: the door. Not sure = Nope stays and it goes on ../shared/runs/not-sure.json (tag Nope), so the next
     run passes over it. Those stay out of the IV and PvP pools (their searches have !#Nope).
--limit N opens at most N. --dry-run changes nothing in step 2 (it still types the door's searches) and skips step 1.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui, base, search, session, door
from base import Skip, log, go
import cleantrades as ct

NOPE = "Nope"
FINAL = ("GIV", "XLX", "2XL", "Transfer", "Reroll", "Luckydex", "Old", "GuaranteedLucky", "Evo", "Special")
HIGH = 42  # IV sum of 93%: may still be in its species' top IV spots


def done_already(dry):
    """step 1: Nope off what already has a final tag"""
    q = f"#{NOPE}&" + ",".join(f"#{t}" for t in FINAL)
    if dry:
        log(f"DRY step 1 skipped: {q}")
        return 0
    n = ct.tag_pile(NOPE, None, off=(NOPE,), query=q)
    log(f"Nope off {n} that already had a final tag")
    return n


def main(limit, dry):
    base.front()
    done_already(dry)
    gate = door.Door(NOPE, scope=f"#{NOPE}")
    from ivc import GYM_DEFENDERS  # (verdict, loaded by Door, puts /ivc on the path)
    passed = gate.listed()
    log(f"door: {sum(passed.values())} on the not-sure list, passed over")
    counts = {"opened": 0}

    def tally(k):
        counts[k] = counts.get(k, 0) + 1

    def visit(i, n, c):
        if passed[(n, c)]:
            passed[(n, c)] -= 1
            return False
        if counts["opened"] >= limit:
            return False
        base.open_tile(i)
        counts["opened"] += 1
        info, texts, _ = base.steady_detail()
        if not base.opened_right(info, n, c):
            raise Skip(f"opened {info['name']!r} but tile said {n!r}")
        if not any(base.is_tag(t, NOPE) for t in info["tags"]):
            raise Skip(f"no Nope tag on detail: {info['tags']}")
        other = [t for t in ("IVC", "PvpC") if any(base.is_tag(x, t) for x in info["tags"])]
        if other:
            what, act = f"has {'+'.join(other)} too: Nope off, {other[0]} decides", lambda: base.set_tags(off=[NOPE])
        else:
            keep, ivs, raws, iv = base.high_iv()
            cp = info["cp"] or c
            sp = ui.species_for(info["name"], info["texts"])
            nick = not sp  # not the species' own name
            sp = sp or base.species_from_candy(texts, cp, info["hp"])
            if keep:
                what = f"{iv}: 98%+, star on, Nope off"
                act = lambda: (base.set_star(True), base.set_tags(off=[NOPE]))
            elif sum(ivs) >= HIGH or nick or any(s in GYM_DEFENDERS for s in sp):
                why = "93%+" if sum(ivs) >= HIGH else f"named {info['name']!r}" if nick else "gym defender"
                what = f"{iv}, {why}: may still be a keeper, back to IVC (name cleared)"

                def act():
                    if nick:
                        base.clear_name()
                    base.set_tags(on=["IVC"], off=[NOPE])
            else:
                if dry:
                    log(f"DRY {n} CP{c} {iv} {'/'.join(sp)}: the door would judge it")
                    tally("door")
                    go("close", "list")
                    return False
                info, texts, _ = base.steady_detail()
                got = gate.judge(info, texts, sp, ivs, (n, c), size=base.extras(texts)[2], raws=raws)
                tally(got)
                log(f"DONE nope door {got} {n!r} CP{c} {iv}")
                go("close", "list")
                return got not in (door.UNSURE,)
        tally(what.split(":")[0] if other else "keep" if keep else "IVC")
        log(f"{'DRY ' if dry else 'DONE '}{n} CP{c}: {what}")
        if not dry:
            act()
        go("close", "list")
        return not dry

    search.start_search(f"#{NOPE}")
    search.walk_list(visit, stop=lambda n: counts["opened"] >= limit)
    log(f"nopes done: {counts}")


def script(a):
    base.start()
    main(session.limit(a), "--dry-run" in a)


if __name__ == "__main__":
    base.new_run_dir(os.path.join(HERE, "runs"))
    session.main(script, sys.argv[1:])
