#!/usr/bin/env python3
"""The last Nope pile: one pass that gives every Pokémon still tagged Nope its final tag, the way /ivc and /pvpc do now
(../shared/door.py). Nothing tags Nope any more. Run it once on each account.

  POGO_PHONE=android caffeinate -dimsu python3 nopes.py [--limit N] [--dry-run]

1. Nope comes off the ones that already have their final tag (an old `tradeable.py tag --nope` that stopped before
   its last step left Nope on next to it). One short search per tag. A search that finds the whole Nope pile is
   misread (a tag this account doesn't have): it's passed over.
2. Walks #Nope&!traded, then #Nope&traded. Each one is opened and appraised:
   - also has IVC or PvpC: Nope off, that skill decides.
   - 98%+ (a shadow: once purified): star on, Nope off. It never goes.
   - may still be a keeper: name cleared, IVC on, Nope off. /ivc names it again and /ivcsort or /pvpc judges it with
     today's rules, door and all. Untraded: 93%+ or a nickname (an old /ivc or Pvp name, XXL ...). Traded or not: a
     gym defender (top 20 CP or IV can't be checked here).
   - the rest: the door. Not sure = Nope stays and it goes on ../shared/runs/not-sure.json (tag Nope), so the next
     run passes over it. Those stay out of the IV and PvP pools (their searches have !#Nope).
--limit N opens at most N. --dry-run only counts in step 1 and changes nothing in step 2 (the door still types its
searches before the walk, but judges nothing).
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui, base, search, session, door, home
from base import Skip, log, go
import cleantrades as ct

NOPE = "Nope"
FINAL = ("GIV", "XLX", "2XL", "Transfer", "Reroll", "Luckydex", "Old", "GuaranteedLucky", "Evo", "Special")
HIGH = 42  # IV sum of 93%: may still be in its species' top IV spots


def done_already(dry):
    """step 1: Nope off what already has a final tag, one tag at a time"""
    total = ct.long_search(f"#{NOPE}")
    log(f"#{NOPE}: {total}")
    off = 0
    for t in FINAL:
        q = f"#{NOPE}&#{t}"
        n = ct.long_search(q)
        if not n:
            continue
        if n >= total:
            log(f"{q}: {n}, the whole pile: a misread (no {t} tag here?), passed over")
            continue
        if dry:
            log(f"DRY {q}: {n} would lose Nope")
            continue
        got = ct.tag_pile(NOPE, None, off=(NOPE,), query=q)
        log(f"{q}: Nope off {got}")
        off += got
    return off


def walk(traded, limit, dry, counts, who):
    """step 2 on #Nope&traded or #Nope&!traded"""
    scope = f"#{NOPE}&{'' if traded else '!'}traded"
    gate = door.Door(NOPE, scope=scope, account=who)
    from ivc import GYM_DEFENDERS  # (verdict, loaded by Door, puts /ivc on the path)
    passed = gate.listed()
    log(f"{scope}: {sum(passed.values())} on the not-sure list, passed over")

    def tally(k):
        counts[k] = counts.get(k, 0) + 1

    def visit(i, n, c):
        if passed[(n, c)]:
            passed[(n, c)] -= 1
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
            tally("other")
        else:
            keep, ivs, raws, iv = base.high_iv()
            cp = info["cp"] or c
            sp = ui.species_for(info["name"], info["texts"])
            nick = not sp  # not the species' own name
            sp = sp or base.species_from_candy(texts, cp, info["hp"])
            gym = any(s in GYM_DEFENDERS for s in sp)
            if keep:
                what = f"{iv}: 98%+, star on, Nope off"
                act = lambda: (base.set_star(True), base.set_tags(off=[NOPE]))
                tally("98%+")
            elif gym or not traded and (sum(ivs) >= HIGH or nick):
                why = "gym defender" if gym else "93%+" if sum(ivs) >= HIGH else f"named {info['name']!r}"
                what = f"{iv}, {why}: may still be a keeper, back to IVC (name cleared)"
                tally("IVC")

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
                got = gate.judge(info, texts, sp, ivs, (n, c), size=base.extras(texts)[2], raws=raws, clear=True)
                tally(got)
                log(f"DONE nope door {got} {n!r} CP{c} {iv}")
                go("close", "list")
                return got != door.UNSURE
        log(f"{'DRY ' if dry else 'DONE '}{n} CP{c}: {what}")
        if not dry:
            act()
        go("close", "list")
        return not dry

    search.start_search(scope)
    search.walk_list(visit, stop=lambda n: counts["opened"] >= limit)


def main(limit, dry):
    base.front()
    who = home.trainer()  # once, first: it ends on the map (the searches start from anywhere)
    done_already(dry)
    counts = {"opened": 0}
    for traded in (False, True):
        if counts["opened"] < limit:
            walk(traded, limit, dry, counts, who)
    log(f"nopes done: {counts}")


def script(a):
    base.start()
    main(session.limit(a), "--dry-run" in a)


if __name__ == "__main__":
    base.new_run_dir(os.path.join(HERE, "runs"))
    session.main(script, sys.argv[1:])
