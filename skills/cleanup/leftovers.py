#!/usr/bin/env python3
"""Tag HashTagAJay's Leftovers saved search by what a trade to another account is worth (CyrillJan, or the user's
wife's account, which is further behind: good for any account, the user 2026-11-16).

  POGO_PHONE=android caffeinate -dimsu python3 leftovers.py [--limit N]   HashTagAJay signed in

HashTagAJay has 360+ Candy XL of most families, so only a trade worth something to the other side goes. Each one is
opened once and gets its final tag at the door (../shared/door.py, ../shared/verdict.py's rules for HashTagAJay):
  regional or Spinda: left as it is, on the not-sure list (a likely special trade: the user tags it by hand)
  GuaranteedLucky > Old > GIV (medal) > 2XL (HashTagAJay has under 360 Candy XL) > Reroll (a new 100 is worth having:
  a mega line, DialgaDex #1 against some raid boss, Master League top 20) > GIV (DialgaDex top 6 against some raid
  boss, or it can Dynamax) > IVC (xxs) > XLX (level 26+: a power-up costs 4 Candy+) > GIV (stage 2 or a hard
  evolution, a 10 or 12 km egg's family, Smeargle, a trade evolution, caught 100 km+ away, a costly line) > Transfer
The species lists are tradeable.py's giver_species() (data: tradeable.py refresh).

Leftovers is the user's: '!4*&!3*&!#&!favorite&!shiny&!lucky&!shadow&!legendary&!mythical&!ultrabeasts&!pvp&!age0-7
&!xxl' (read off the iPhone 2026-11-16). Its !# and !favorite drop each one judged (a tag or a star) out of it. The
walk adds &!gigantamax (a special trade it doesn't leave out). --limit N stops after N opened.
"""
import os, sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import base
from base import Stop, log
import home, session
import tradeable
from rules import GIVER, TAKER

SHORTCUT = "Leftovers"
SUFFIX = "&!gigantamax"  # the Gigantamax ones are special trades: Leftovers doesn't leave them out


def gone(got, gate):
    """did the door's answer take this one out of Leftovers? Any tag (!#) or a star (!favorite) does"""
    return got == "keep" or got == "tag" and bool(gate.last.tags or gate.last.star)


def cmd_door(limit):
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="leftovers")
    who = home.trainer()
    if who != TAKER:
        raise Stop(f"signed in as {who!r}: Leftovers is {TAKER}'s ({GIVER}'s pile is tradeable.py)")
    home.start()
    got = tradeable.door_walk(SUFFIX, limit, who, shortcut=SHORTCUT, gone=gone)
    log(f"Leftovers, through the door: {dict(got)}")


if __name__ == "__main__":
    session.main(cmd_door, session.limit(sys.argv[1:]))
