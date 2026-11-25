#!/usr/bin/env python3
"""Tag HashTagAJay's Leftovers saved search by what a trade to another account is worth (CyrillJan, or the user's
wife's account, which is further behind: good for any account, the user 2026-11-16).

  POGO_PHONE=android caffeinate -dimsu python3 leftovers.py [--limit N]   from either account
  POGO_PHONE=android caffeinate -dimsu python3 leftovers.py again GIV|Transfer|Reroll [--as CyrillJan] [--and Q] [--limit N]
                                          re-judge a tag pile

Signed in as someone else on the Pixel, it switches to HashTagAJay first (../shared/account.py) and goes on.
Then cleantrades.py's steps run first, every time (the user, 2026-11-24): the shortcuts' tags, then Clean Trades
tagged Transfer in bulk (its door ones, legendaries and such, opened one by one). A traded one in Leftovers is a Clean
Trades one, so none is left here to open. --limit N goes to cleantrades too (at most N power-ups).

HashTagAJay has 360+ Candy XL of most families, so only a trade worth something to the other side goes. Each one is
opened once and gets its final tag at the door (../shared/door.py, ../shared/verdict.py's rules for HashTagAJay):
  regional or Spinda: left as it is, on the not-sure list (a likely special trade: the user tags it by hand)
  GuaranteedLucky > Old > GIV (medal) > 2XL (HashTagAJay has under 360 Candy XL) > Reroll (a new 100 is worth having:
  the best mega of a type, DialgaDex top 6 against some 4-star+ raid boss (#2-#6 was GIV, the user 2026-11-19), Master
  League top 20) > IVC (xxs) > GIV (level 26+: a power-up costs 4 Candy+) > GIV (stage 2 or a hard
  evolution, a 10 or 12 km egg's family, Smeargle, a gym defender's line (Slakoth, Wynaut...), a Dynamax one, a trade evolution, caught 100 km+ away, a costly line)
  > GIV (one that can Dynamax, while this account has 1,000 Candy or less, or 360 + one Max Move's Candy XL or less) > Transfer
The species lists are tradeable.py's giver_species() (data: tradeable.py refresh).

Leftovers is the user's: '!4*&!3*&!#&!favorite&!shiny&!lucky&!shadow&!legendary&!mythical&!ultrabeasts&!pvp&!age0-7
&!xxl&!gigantamax' (read off the iPhone 2026-11-16, !gigantamax added 2026-11-19). Its !# and !favorite drop each
one judged (a tag or a star) out of it. --limit N stops after N opened.

again GIV|Transfer|Reroll: HashTagAJay's #GIV, #Transfer or #Reroll pile (Reroll: the user, 2026-11-20), each one judged again under today's rules (the user,
2026-11-16). The door takes the pile's tag off and gives the verdict's (GIV again: it stays). Not sure: left as it is.
Left out: legendary, mythical, Ultra Beast, Gigantamax (special trades: by hand) and ones with IVC or PvpC too (/ivc
or /pvpc judge those). Each one judged is written to runs/again-done.json under the rules' hash, so a rerun, or the
other pile's walk, passes over it (new rules: judged again).
--as CyrillJan: CyrillJan's pile instead, judged for HashTagAJay (tradeable.py's rules: the user, 2026-11-20). --and Q:
only the ones that also fit Q ('&'-joined after the pile's search), for a pile too big to walk whole. Q must not end in
a count term (countcandy...): the door adds its own terms after it, and a count term eats what follows.
"""
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import base
from base import Stop, log, go
import ui
import home, session, account
import tradeable
from rules import GIVER, TAKER

SHORTCUT = "Leftovers"
SUFFIX = ""  # Leftovers leaves out the special trades itself, Gigantamax too (rules.SAVED, the user 2026-11-19)


def gone(got, gate):
    """did the door's answer take this one out of Leftovers? Any tag (!#) or a star (!favorite) does"""
    return got == "keep" or got == "tag" and bool(gate.last.tags or gate.last.star)


def cmd_door(limit):
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="leftovers")
    who = home.trainer()
    if who != TAKER:
        if not ui.ANDROID:  # account.py signs in on the Pixel only
            raise Stop(f"signed in as {who!r}: Leftovers is {TAKER}'s ({GIVER}'s pile is tradeable.py)")
        log(f"signed in as {who!r}: Leftovers is {TAKER}'s, switching")
        who = account.switch(TAKER)
    home.start()
    import cleantrades  # every time, first: a traded one in Leftovers is a Clean Trades one, tagged there in bulk
    cleantrades.clean(limit, who)  # (Transfer) instead of opened here (64 opened that way, 2026-11-16 and 11-18)
    home.start()
    got = tradeable.door_walk(SUFFIX, limit, who, shortcut=SHORTCUT, gone=gone)
    log(f"Leftovers, through the door: {dict(got)}")


PILES = ("GIV", "Transfer", "Reroll")
AGAIN_SKIP = "&!legendary&!mythical&!ultrabeasts&!gigantamax&!#IVC&!#PvpC"  # ends in C: no thin last letter
AGAIN_DONE = os.path.join(HERE, "runs", "again-done.json")


def again_done():
    try:
        return json.load(open(AGAIN_DONE))
    except (OSError, ValueError):
        return {}


def cmd_again(tag, limit, owner=TAKER, narrow=""):
    """each one in owner's #tag (and narrow, when given) judged again at the door: the pile's tag off, the verdict's on
    -> Counter of what happened"""
    import door, search
    from ivc import GYM_DEFENDERS  # noqa: F401 (verdict, loaded by Door, needs /ivc on the path)
    base.new_run_dir(os.path.join(HERE, "runs"), suffix=f"again-{tag.lower()}")
    who = home.trainer()
    if who != owner:
        if not ui.ANDROID:  # account.py signs in on the Pixel only
            raise Stop(f"signed in as {who!r}: this again is for {owner}'s piles")
        log(f"signed in as {who!r}: switching to {owner}")
        who = account.switch(owner)
    home.start()
    scope = f"#{tag}{AGAIN_SKIP}" + (f"&{narrow.lstrip('&')}" if narrow else "")
    gate = door.Door(tag, scope=scope, account=who, rank_gym=True)  # no find: the pile's own tag comes off
    key = f"{who}|{door.RULES}"  # both piles: one GIV just moved to Transfer isn't opened again in the Transfer walk
    memo = again_done()
    done = Counter(map(tuple, memo.get(key, [])))
    passed = gate.listed()
    log(f"again {tag}: {sum(done.values())} judged under these rules already, {sum(passed.values())} not sure: "
        "passed over")
    counts = Counter()

    def visit(i, n, c):
        for skip in (passed, done):
            if skip[(n, c)]:
                skip[(n, c)] -= 1
                return False
        counts["opened"] += 1
        got, iv = gate.judge_open(i, n, c)
        counts[got] += 1
        v = getattr(gate, "last", None)
        stays = got == door.UNSURE or (got == "tag" and v is not None and tag in v.tags)
        log(f"DONE again {got} {'+'.join(v.tags) if v else ''} {n!r} CP{c} {iv}: {'stays in' if stays else 'left'} #{tag}")
        go("close", "list")
        if got != door.UNSURE:  # judged: a rerun (or the other pile's walk) under these rules passes over it
            memo.setdefault(key, []).append([n, c])
            with open(AGAIN_DONE, "w") as fh:
                json.dump(memo, fh)
        return not stays

    _, texts, _ = search.start_search(scope)
    log(f"again {tag}: the game counts {search.result_count(texts)} in {scope}")
    search.walk_list(visit, stop=lambda n: counts["opened"] >= limit)
    log(f"again {tag}, through the door: {dict(counts)}")
    return counts


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "again":
        if len(a) < 2 or a[1] not in PILES:
            sys.exit(__doc__)
        owner = a[a.index("--as") + 1] if "--as" in a else TAKER
        if owner not in (GIVER, TAKER):
            sys.exit(__doc__)
        session.main(cmd_again, a[1], session.limit(a), owner, a[a.index("--and") + 1] if "--and" in a else "")
    else:
        session.main(cmd_door, session.limit(a))
