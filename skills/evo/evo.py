#!/usr/bin/env python3
"""Evolve every free trade evolution tagged Evo, as fast as the game lets it. CyrillJan on the Pixel only: the Mac stays
free, and HashTagAJay doesn't need the XP.

  POGO_PHONE=android python3 evo.py [--limit N] [--dry-run] [--here] [--candy]

Signed in as HashTagAJay: it switches to CyrillJan first, and the phone stays on CyrillJan after. A Lucky Egg is up to
the user: switch first (pogo.py account CyrillJan), pop it, then run this.

The search is rules.EVO + evolve + traded + !xxl + rules.TRADE_EVOS (dex numbers), sorted by RECENT. An evolved one isn't one
of those numbers any more, so it drops out, and the top tile is the next one each time.

For each one: read the EVOLVE row, tap it, read YES, tap it, wait out the animation, X, the top tile. Only two looks: the
EVOLVE row moves with the page's rows, and YES moves with the box (0.60, 0.70, 0.74 seen, with NO right under it).
It stops rather than guesses:
- A cost on the EVOLVE row: this search should only find free ones, so no candy is spent unless --candy says so.
- No EVOLVE row: the list is empty, still shows an evolved one, or a tap was lost. It searches again once, then stops.
- Anything else in the way after the animation (a level-up, a medal) shows up as no EVOLVE row: the same new search, then
  a stop with a capture in the run folder.

--here starts from the Pokémon list on screen (a tag's list, your own search) as it is. It doesn't check the account.
--dry-run goes as far as the YES / NO box for the top one and taps NO. It still taps the phone.
Log in runs/<time>-android/log.txt.
"""
import argparse, os, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log, keep_capture, look
import search, session, home, account
from evolve import evolve_one
from taps import settled_tiles
from tagsheet import search_exact
from rules import EVO, EVO_FOR, TRADE_EVOS

SEARCH = f"#{EVO}&evolve&traded&!xxl&{TRADE_EVOS}"  # an XXL one stays as it is (the user, 2026-11-05)
def script(limit, dry, here, candy):
    if not ui.ANDROID:
        raise Stop("evo.py is Pixel only: POGO_PHONE=android")
    if here:
        session.ready()
        if look()[0] == "detail":  # left open on one: its list is under it
            base.go("close", "list")
    else:
        who = home.trainer()
        if who != EVO_FOR:
            account.switch(EVO_FOR)
        base.start()
        search_exact(SEARCH)
        if not settled_tiles():
            log(f"nothing in {SEARCH}")
            return
        _, texts, _, bounds = look()
        log(f"{SEARCH}: {search.result_count(texts)} to evolve")
        search.sort_recent(bounds)
    screen, texts, _, bounds = look()
    if not ui.tiles(texts):
        keep_capture("nolist")
        raise Stop(f"no Pokémon list on screen ('{screen}')")
    spot = ui.tiles(texts)[0][2:]  # the top tile. It doesn't move while the list stays at the top
    base.go("tile 1", "detail")
    done, retried = 0, False
    t0 = time.time()
    while done < limit:
        page = evolve_one(dry, candy)
        if not page:
            if here:
                log("no EVOLVE row: the list on screen is done, or something's in the way")
                keep_capture("noevolve")
                break
            if retried:
                keep_capture("noevolve")
                raise Stop("the top tile has no EVOLVE row, after a new search too")
            log("  no EVOLVE row: searching again")  # the list is empty, didn't update, or a tap was lost
            retried = True
            if look()[0] != "list":
                base.go("close", "list")
            search_exact(SEARCH)
            if not settled_tiles():
                break
            base.go("tile 1", "detail")
            continue
        retried = False
        done += 1
        log(f"{done} done, {(time.time() - t0) / done:.1f}s each")
        if dry or done >= limit:
            break
        base.tap_x(page)  # no looks here: the next page's read checks it all, as the taps can do no harm
        time.sleep(0.45)
        base.click(*spot, page)
    log(f"done: {done} {'looked at' if dry else 'YES tapped'}")


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--limit", type=int, default=10 ** 9, help="at most N evolutions this run")
    ap.add_argument("--dry-run", action="store_true", help="the top one, up to the YES / NO box, then NO")
    ap.add_argument("--candy", action="store_true", help="evolve the ones that cost candy too")
    ap.add_argument("--here", action="store_true", help="the list on screen: no account check, search or sort")
    a = ap.parse_args()
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="android")
    session.main(script, a.limit, a.dry_run, a.here, a.candy)


if __name__ == "__main__":
    main()
